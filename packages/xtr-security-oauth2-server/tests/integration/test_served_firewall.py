"""An API read by this deployment's own access tokens, served for real.

One process issues the tokens and reads them, which is the deployment the
resource-server side is documented for: the firewall on ``/api`` accepts
exactly what the token endpoint hands out.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from xtr_dependency_injection import Injected
from xtr_security import Security

from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    client_credentials_token,
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
    text_fields,
)

pytestmark = pytest.mark.anyio

FIREWALL = "api"


def _api(app: FastAPI) -> None:
    """Mount an API behind the firewall that reads this server's access tokens."""
    # The dependency is handed to the router before any route is added: the
    # framework copies a router's dependencies into each route as it arrives.
    router = APIRouter(prefix="/api")

    @router.get("/me")
    async def me(security: Injected[Security]) -> dict[str, object]:
        token = security.get_token()
        assert token is not None

        return {
            "caller": token.get_user_identifier(),
            "roles": list(token.get_role_names()),
        }

    @router.get("/writable")
    async def writable() -> dict[str, str]:
        return {"wrote": "yes"}

    app.include_router(router)


def _application() -> FastAPI:
    """Return the served application with its API behind the firewall."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_firewall_app"),
        _api,
    )


async def test_a_request_carrying_no_token_is_challenged_for_one() -> None:
    async with serving(_application()) as client:
        answered = await client.get("/api/me")

    assert answered.status_code == 401
    # The challenge says what would have worked, and nothing else: RFC 6750
    # section 3 has the scheme followed by one or more auth-param values, and
    # section 3.1 asks that a request lacking any authentication information
    # be told no error code.
    assert answered.headers["www-authenticate"] == f'Bearer realm="{FIREWALL}"'


async def test_the_challenge_is_never_cached() -> None:
    # A proxy answering another caller's request with one principal's refusal
    # would be telling the wrong person something about the right one.
    async with serving(_application()) as client:
        answered = await client.get("/api/me")

    assert answered.headers["cache-control"] == "no-store"


async def test_a_token_a_client_was_issued_for_itself_names_the_client_as_the_caller() -> None:
    # Such a token belongs to no person, so the client stands where a resource
    # owner would.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert answered.status_code == 200
    assert text_field(json_of(answered), "caller") == CLIENT_ID


async def test_a_scope_reaches_the_authorization_rules_as_a_role() -> None:
    # What lets an access token be checked by exactly the same rules as
    # everything else.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert "ROLE_OAUTH2_READ" in text_fields(json_of(answered), "roles")


async def test_a_token_without_the_scope_a_route_asks_for_is_refused() -> None:
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get("/api/writable", headers={"Authorization": f"Bearer {token}"})

    assert answered.status_code == 403
    # What the caller is told, not only that it was refused: RFC 6750 2 names
    # ``insufficient_scope`` for a token good enough to prove the caller and
    # not good enough for what it asked to do — in the challenge header, the
    # one place RFC 6750 reserves for it, and nowhere in the body.
    assert answered.text == ""
    assert 'error="insufficient_scope"' in answered.headers["WWW-Authenticate"]
    assert answered.headers["WWW-Authenticate"].startswith("Bearer")


async def test_a_token_this_server_did_not_sign_is_refused() -> None:
    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer not.a.token"},
        )

    assert answered.status_code == 401


async def test_a_request_whose_header_names_another_scheme_is_not_claimed() -> None:
    # This authenticator reads bearer tokens; anything else is somebody
    # else's to answer, and with no other authenticator the firewall
    # challenges.
    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": "Basic YWRhOnNlY3JldA=="},
        )

    assert answered.status_code == 401


async def test_a_withdrawn_token_stops_opening_the_api() -> None:
    # What withdrawing a token is *for*: the reading an API does has to judge
    # revocation against the same store the withdrawal wrote to, or a token
    # given up would keep working until it expired.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        bearer = {"Authorization": f"Bearer {token}"}
        before = await client.get("/api/me", headers=bearer)
        withdrawn = await client.post(
            "/revoke",
            data={
                "token": token,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        after = await client.get("/api/me", headers=bearer)

    assert before.status_code == 200
    assert withdrawn.status_code == 200
    assert after.status_code == 401
