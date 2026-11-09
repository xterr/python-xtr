"""When the end-user signed in, as a served ID token states it.

The deployment signs the end-user in with a form, on a stateful firewall, so
the token the firewall keeps records when they proved their password. The
deployment's consent listener approves at the default priority, after the
provider has read that time off the token; the ID token then states it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest
from xtr_clock import Clock, MockClock
from xtr_http_kernel.testing import override_services

from tests.fixtures.openid_app.config import (
    FORM_LOGIN_ENV,
    SECOND_USER_IDENTIFIER,
    SECOND_USER_PASSWORD,
    USER_IDENTIFIER,
    USER_PASSWORD,
)
from tests.support.served import (
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE,
    VERIFIER,
    claims_of,
    code_challenge_of,
    json_of,
    openid_kernel,
    redirected_with,
    served_application,
    serving,
    text_field,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

pytestmark = pytest.mark.anyio

#: How far apart the two end-users sign in.
_MINUTE: Final = 60


async def _log_in(client: httpx.AsyncClient, identifier: str, password: str) -> None:
    """Sign in with the form, the session keeping the login for the next request."""
    answered = await client.post(
        "/login_check",
        params={"_username": identifier, "_password": password},
    )
    assert answered.status_code == 302, answered.text


async def _signed_in(client: httpx.AsyncClient) -> Mapping[str, object]:
    """Ask for a code as the logged-in end-user, redeem it, and return the ID token's claims."""
    authorized = await client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "code_challenge": code_challenge_of(VERIFIER),
            "code_challenge_method": "S256",
        },
    )
    answered = await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code": redirected_with(authorized)["code"],
            "code_verifier": VERIFIER,
        },
    )
    assert answered.status_code == 200, answered.text

    return claims_of(text_field(json_of(answered), "id_token"))


def _seconds(clock: MockClock) -> int:
    """Return where ``clock`` stands, in seconds since the epoch."""
    return int(clock.now().timestamp())


async def test_the_id_token_states_when_the_end_user_signed_in() -> None:
    # Frozen at the current instant, so whatever reads the system clock rather
    # than the application's agrees with it.
    clock = MockClock()
    app = served_application(openid_kernel(FORM_LOGIN_ENV))

    with override_services(app, {Clock: Clock(clock)}):
        async with serving(app) as client:
            await _log_in(client, USER_IDENTIFIER, USER_PASSWORD)
            logged_in_at = _seconds(clock)
            claims = await _signed_in(client)

    auth_time = claims["auth_time"]
    assert isinstance(auth_time, int)
    assert abs(auth_time - logged_in_at) <= 5


async def test_each_sign_in_states_its_own_end_users_sign_in_time() -> None:
    clock = MockClock()
    app = served_application(openid_kernel(FORM_LOGIN_ENV))

    with override_services(app, {Clock: Clock(clock)}):
        async with serving(app) as client:
            await _log_in(client, USER_IDENTIFIER, USER_PASSWORD)
            first_login = _seconds(clock)
            first = await _signed_in(client)
            clock.sleep(_MINUTE)
            await _log_in(client, SECOND_USER_IDENTIFIER, SECOND_USER_PASSWORD)
            second_login = _seconds(clock)
            second = await _signed_in(client)

    assert (first["sub"], first["auth_time"]) == (USER_IDENTIFIER, first_login)
    assert (second["sub"], second["auth_time"]) == (SECOND_USER_IDENTIFIER, second_login)
    assert second_login - first_login == _MINUTE
