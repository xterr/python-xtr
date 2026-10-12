"""Every shipped flow driven through a database, served for real.

What this proves is the one thing a double cannot: the managers are singletons
— one per application, as every other service of this package is — and each of
them asks the connection registry for the session of *the request being
served*, every time it reads or writes. A manager handed a session when it was
built would be holding the first request's session for the life of the process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import anyio
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from xtr_dependency_injection import Injected
from xtr_security_http.firewall.firewall import Firewall

from tests.fixtures.oauth2_orm_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.support.orm_app import orm_kernel, stored_tables
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    SCOPE,
    SEED_PATH,
    code_challenge_of,
    json_of,
    served_application,
    serving,
    text_field,
)
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    import httpx

pytestmark = pytest.mark.anyio

#: A proof key, within the length the standard allows.
VERIFIER: Final = "a-code-verifier-long-enough-for-the-standard"

#: What a client sends to tie the authorization request to that proof key.
CHALLENGE: Final = code_challenge_of(VERIFIER)

#: What ties the redirect back to the browser that started the flow.
STATE: Final = "the-stored-opaque-state"

#: Where a request says which session the stored client manager read through.
PROBE_PATH: Final = "/which-session"

#: An API path the firewall claims, so a withdrawn token can be seen to be.
API_PATH: Final = "/api/orders"

#: How many requests race through the probe at once.
_CONCURRENT: Final = 2


def _routes(app: FastAPI) -> None:
    """Add the application's own routes: one probe and one protected resource."""

    @app.get(PROBE_PATH)
    async def which_session(
        clients: Injected[ClientManagerInterface],
        session: Injected[AsyncSession],
    ) -> dict[str, object]:
        """Read a client through the shared manager, and say which session saw it."""
        found = await clients.find(CLIENT_ID)

        return {
            "found": found is not None,
            "read_in_this_session": found is not None and found in session.sync_session,
            "session": id(session),
        }

    @app.get(API_PATH)
    async def orders() -> dict[str, str]:
        """Answer a caller the firewall let through."""
        return {"orders": "none"}


def _application(tmp_path: Path) -> FastAPI:
    """Return the served application of the stored deployment."""
    return served_application(
        orm_kernel(tmp_path),
        extend=_routes,
        dependencies=[Firewall()],
    )


def _redirect_params(response: httpx.Response) -> Mapping[str, str]:
    """Return the parameters the authorization response was delivered in."""
    return dict(parse_qsl(urlsplit(response.headers["location"]).query))


async def _seed(client: httpx.AsyncClient) -> None:
    """Register a confidential client that may drive every flow."""
    seeded = await client.post(SEED_PATH, params={"grant": "", "redirect_uri": REDIRECT_URI})
    assert seeded.status_code == 200, seeded.text


async def _owner_token(client: httpx.AsyncClient) -> str:
    """Establish the resource owner, and return the token that proves them."""
    issued = json_of(
        await client.post(
            "/token",
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": USER_IDENTIFIER,
                "password": USER_PASSWORD,
                "scope": SCOPE,
            },
        ),
    )

    return text_field(issued, "access_token")


async def _code(client: httpx.AsyncClient) -> str:
    """Drive the first half of the redirect flow and return the code it issued."""
    answered = await client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "state": STATE,
            "scope": SCOPE,
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
        },
        headers={"Authorization": f"Bearer {await _owner_token(client)}"},
    )
    delivered = _redirect_params(answered)
    assert "code" in delivered, f"{answered.status_code}: {delivered}"

    return delivered["code"]


async def test_a_client_acting_for_itself_is_issued_a_stored_token(tmp_path: Path) -> None:
    async with stored_tables(tmp_path), serving(_application(tmp_path)) as client:
        _ = await client.post(SEED_PATH)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

        assert answered.status_code == 200, answered.text
        assert text_field(json_of(answered), "access_token")


async def test_a_code_is_redeemed_for_a_stored_token_pair(tmp_path: Path) -> None:
    async with stored_tables(tmp_path), serving(_application(tmp_path)) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": await _code(client),
                "code_verifier": VERIFIER,
            },
        )

        assert answered.status_code == 200, answered.text
        issued = json_of(answered)
        assert text_field(issued, "access_token")
        assert text_field(issued, "refresh_token")


async def test_a_stored_refresh_token_is_spent_exactly_once(tmp_path: Path) -> None:
    async with stored_tables(tmp_path), serving(_application(tmp_path)) as client:
        await _seed(client)
        pair = json_of(
            await client.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                    "code": await _code(client),
                    "code_verifier": VERIFIER,
                },
            ),
        )
        form = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": text_field(pair, "refresh_token"),
        }

        refreshed = await client.post("/token", data=form)
        spent_again = await client.post("/token", data=form)

        assert refreshed.status_code == 200, refreshed.text
        assert text_field(json_of(refreshed), "access_token")
        assert spent_again.status_code == 400
        assert text_field(json_of(spent_again), "error") == "invalid_grant"


async def test_a_stored_token_is_withdrawn_by_the_revocation_endpoint(tmp_path: Path) -> None:
    async with stored_tables(tmp_path), serving(_application(tmp_path)) as client:
        _ = await client.post(SEED_PATH)
        issued = json_of(
            await client.post(
                "/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                },
            ),
        )
        token = text_field(issued, "access_token")
        before = await client.get(API_PATH, headers={"Authorization": f"Bearer {token}"})

        withdrawn = await client.post(
            "/revoke",
            data={"token": token, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )
        after = await client.get(API_PATH, headers={"Authorization": f"Bearer {token}"})

        assert before.status_code == 200, before.text
        assert withdrawn.status_code == 200, withdrawn.text
        assert after.status_code == 401


async def test_the_introspection_endpoint_reads_a_stored_token(tmp_path: Path) -> None:
    async with stored_tables(tmp_path), serving(_application(tmp_path)) as client:
        _ = await client.post(SEED_PATH)
        issued = json_of(
            await client.post(
                "/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                },
            ),
        )

        answered = await client.post(
            "/introspect",
            data={
                "token": text_field(issued, "access_token"),
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

        assert answered.status_code == 200, answered.text
        described = json_of(answered)
        assert described["active"] is True
        assert text_field(described, "client_id") == CLIENT_ID


async def test_two_requests_at_once_read_through_two_different_sessions(
    tmp_path: Path,
) -> None:
    async with stored_tables(tmp_path), serving(_application(tmp_path)) as client:
        _ = await client.post(SEED_PATH)
        answers: list[Mapping[str, object]] = []

        async def probe() -> None:
            answers.append(json_of(await client.get(PROBE_PATH)))

        async with anyio.create_task_group() as group:
            for _ in range(_CONCURRENT):
                _ = group.start_soon(probe)

        assert len(answers) == _CONCURRENT
        for answer in answers:
            # The shared manager read the client, and the instance it handed
            # back belongs to the session of the request that asked.
            assert answer["found"] is True
            assert answer["read_in_this_session"] is True
        assert len({answer["session"] for answer in answers}) == _CONCURRENT
