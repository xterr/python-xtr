"""A resource owner's own credentials, and the refresh token that follows.

The one shipped flow that issues a refresh token without a browser, so it is
also where rotation and the refusal to reuse a spent token are driven.
"""

from __future__ import annotations

import anyio
import httpx
import pytest
from fastapi import APIRouter, FastAPI
from xtr_dependency_injection import Injected
from xtr_security import Security
from xtr_security_http.firewall.firewall import Firewall

from tests.fixtures.oauth2_password_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.fixtures.oauth2_password_app.listeners import ISSUED
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SCOPE,
    claims_of,
    json_of,
    oauth2_kernel,
    seed_any_grant_client,
    served_application,
    serving,
    text_field,
    text_fields,
)

pytestmark = pytest.mark.anyio


def _api(app: FastAPI) -> None:
    """Mount one route behind the firewall that reads this server's tokens."""
    api = Firewall("api")
    router = APIRouter(prefix="/api", dependencies=[api])

    @router.get("/me")
    async def me(security: Injected[Security]) -> dict[str, object]:
        token = security.get_token()
        assert token is not None

        return {
            "caller": token.get_user_identifier(),
            "roles": list(token.get_role_names()),
        }

    app.include_router(router)


def _application() -> FastAPI:
    """Return the served application of the password-and-refresh deployment."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_password_app"),
        _api,
    )


def _password_form(password: str = USER_PASSWORD) -> dict[str, str]:
    """Return the form a client sends a resource owner's credentials in."""
    return {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": USER_IDENTIFIER,
        "password": password,
        "scope": SCOPE,
    }


async def test_a_resource_owners_credentials_are_exchanged_for_a_token_pair() -> None:
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post("/token", data=_password_form())

    assert answered.status_code == 200
    issued = json_of(answered)
    assert text_field(issued, "access_token")
    # The flow that knows who the person is is the one that may hand out a
    # credential outliving the access token.
    assert text_field(issued, "refresh_token")


async def test_the_token_names_the_resource_owner_rather_than_the_client() -> None:
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        issued = json_of(await client.post("/token", data=_password_form()))

    claims = claims_of(text_field(issued, "access_token"))

    assert text_field(claims, "sub") == USER_IDENTIFIER


async def test_credentials_this_deployment_does_not_accept_are_refused() -> None:
    # The listener leaves the user unresolved, and the refusal does not say
    # which half was wrong.
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post("/token", data=_password_form("not-the-password"))

    assert answered.status_code in {400, 401}
    assert text_field(json_of(answered), "error") != "invalid_scope"


async def test_the_application_hears_that_a_token_was_issued() -> None:
    ISSUED.clear()

    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        _ = await client.post("/token", data=_password_form())

    assert ISSUED == ["oauth2_server.access_token.issued"]


async def test_a_refresh_token_is_exchanged_for_a_fresh_pair() -> None:
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        first = json_of(await client.post("/token", data=_password_form()))
        answered = await client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": text_field(first, "refresh_token"),
            },
        )

    assert answered.status_code == 200
    rotated = json_of(answered)
    assert text_field(rotated, "access_token") != text_field(first, "access_token")
    assert text_field(rotated, "refresh_token") != text_field(first, "refresh_token")


async def test_a_refresh_token_that_was_already_spent_is_refused() -> None:
    # Rotation only protects anything if the spent credential stops working.
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        first = json_of(await client.post("/token", data=_password_form()))
        spent = text_field(first, "refresh_token")
        form = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": spent,
        }
        _ = await client.post("/token", data=form)
        answered = await client.post("/token", data=form)

    # The standard names this one: a refresh token that is invalid, expired or
    # revoked is an `invalid_grant`, and that is a 400. The reference server
    # answers `invalid_request` with a 401 here, which this port does not
    # follow.
    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_grant"


async def test_two_refreshes_of_one_token_at_once_yield_exactly_one_token() -> None:
    # Both requests read the stored token before either withdrew it, so only an
    # atomic withdrawal can decide between them. Without one, a refresh token
    # could be spent twice by racing it against itself.
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        first = json_of(await client.post("/token", data=_password_form()))
        form = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": text_field(first, "refresh_token"),
        }
        answered: list[httpx.Response] = []

        async def spend() -> None:
            answered.append(await client.post("/token", data=form))

        async with anyio.create_task_group() as racing:
            _ = racing.start_soon(spend)
            _ = racing.start_soon(spend)

    issued = [answer for answer in answered if answer.status_code == 200]
    refused = [answer for answer in answered if answer.status_code != 200]

    assert len(issued) == 1
    assert len(refused) == 1
    assert text_field(json_of(refused[0]), "error") == "invalid_grant"


async def test_the_caller_holds_their_own_roles_beside_the_tokens_scopes() -> None:
    # A token grants on top of who somebody is, not instead of it.
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        issued = json_of(await client.post("/token", data=_password_form()))
        answered = await client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {text_field(issued, 'access_token')}"},
        )

    assert answered.status_code == 200
    document = json_of(answered)
    assert text_field(document, "caller") == USER_IDENTIFIER
    granted = text_fields(document, "roles")
    assert "ROLE_OAUTH2_READ" in granted
    assert "ROLE_USER" in granted
