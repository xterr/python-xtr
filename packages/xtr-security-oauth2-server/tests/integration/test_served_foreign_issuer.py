"""A token signed with the right key, claiming the wrong issuer, is refused.

The reading deployment here keeps no record of its tokens, so there is nothing
that could read as withdrawn: a token presented to it is refused only for what
it says. That is what lets the pair below isolate one claim — the two tokens
differ in their issuer and in nothing else.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final

import pytest
from fastapi import APIRouter, FastAPI
from xtr_dependency_injection import Injected
from xtr_security import Security
from xtr_security_http.firewall.firewall import Firewall

from tests.support.served import (
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
)
from tests.support.signing import ISSUER
from tests.support.tokens import signed_access_token

pytestmark = pytest.mark.anyio

#: Another authorization server, signing with the very same key — the case a
#: shared or leaked key makes real.
FOREIGN_ISSUER: Final = "https://another-authorization-server.example.com"

#: The client the tokens below are issued to. No person is named, so the
#: caller stands for the client itself and no user provider is consulted.
CLIENT_ID: Final = "client-1"


def _api(app: FastAPI) -> None:
    """Mount one route behind the firewall that reads this server's tokens."""
    api = Firewall("api")
    router = APIRouter(prefix="/api", dependencies=[api])

    @router.get("/me")
    async def me(security: Injected[Security]) -> dict[str, object]:
        token = security.get_token()
        assert token is not None

        return {"caller": token.get_user_identifier()}

    app.include_router(router)


def _application() -> FastAPI:
    """Return the reading deployment, with an API behind its firewall."""
    return served_application(oauth2_kernel("tests.fixtures.oauth2_reader_app"), _api)


def _token(issuer: str) -> str:
    """Return a really signed access token claiming ``issuer``.

    Stamped against the clock the application actually runs on, so that the
    only thing in question is the issuer: a token minted against a frozen
    instant would be refused for having expired instead.
    """
    return signed_access_token(
        client_id=CLIENT_ID,
        user_identifier=None,
        issuer=issuer,
        lifetime=timedelta(hours=1),
        now=datetime.now(UTC),
    )


async def test_a_token_claiming_this_server_is_accepted() -> None:
    # The control: everything about this token is what the reader expects, so
    # the pair below differs in the issuer alone.
    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {_token(ISSUER)}"},
        )

    assert answered.status_code == 200
    assert text_field(json_of(answered), "caller") == CLIENT_ID


async def test_a_token_claiming_another_server_is_refused() -> None:
    # Signed with the same key, so the signature checks out; refused for the
    # issuer it names. Without this check, every server sharing a key could
    # mint tokens for every other.
    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {_token(FOREIGN_ISSUER)}"},
        )

    assert answered.status_code == 401
    # A token was presented and failed a check, so the challenge names the
    # error code RFC 9068 section 4 requires of any such failure — and only
    # the public text beside it, never which check it was.
    assert answered.headers["www-authenticate"] == (
        'Bearer error="invalid_token", error_description="The access token could not be accepted."'
    )


async def test_an_expired_token_is_refused_however_it_is_signed() -> None:
    expired = signed_access_token(
        client_id=CLIENT_ID,
        user_identifier=None,
        issuer=ISSUER,
        lifetime=timedelta(hours=-1),
        now=datetime.now(UTC),
    )

    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {expired}"},
        )

    assert answered.status_code == 401
