"""``prompt`` and ``max_age``, decided by the provider's step in the login firewall's chain.

The deployment signs the end-user in with a form on a stateful firewall that
lists the prompt step, so a request asking for a fresh sign-in is sent to the
login page and comes back to the authorization endpoint once it is made. One
more deployment lists the step on a firewall that keeps no session, which has
nowhere to keep the request while the end-user signs in.

What is left of ``prompt`` once the step is done with it is the application's:
the deployment's consent listener reads it, and answers the one client its
consent was never given for either with a refusal or with its consent page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import pytest
from xtr_clock import Clock, MockClock
from xtr_http_kernel.testing import override_services

from tests.fixtures.openid_app.config import (
    PROMPT_ENV,
    STATELESS_PROMPT_ENV,
    USER_IDENTIFIER,
    USER_PASSWORD,
)
from tests.fixtures.openid_app.listeners import CONSENT_PAGE
from tests.support.served import (
    CLIENT_ID,
    CONSENT_CLIENT_ID,
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
from xtr_security_openid_connect_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    import httpx

pytestmark = pytest.mark.anyio

_STATE: Final = "xyz"
_LOGIN_PATH: Final = "/login"
_MINUTE: Final = 60


@pytest.fixture
def clock() -> MockClock:
    # Frozen at the current instant, so whatever reads the system clock rather
    # than the application's agrees with it until a test moves it.
    return MockClock()


@pytest.fixture
async def client(clock: MockClock) -> AsyncGenerator[httpx.AsyncClient]:
    app = served_application(openid_kernel(PROMPT_ENV))
    with override_services(app, {Clock: Clock(clock)}):
        async with serving(app) as served:
            yield served


def _query(**extra: str) -> dict[str, str]:
    return {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": _STATE,
        "code_challenge": code_challenge_of(VERIFIER),
        "code_challenge_method": "S256",
        **extra,
    }


async def _authorize(client: httpx.AsyncClient, **extra: str) -> httpx.Response:
    return await client.get("/authorize", params=_query(**extra))


async def _log_in(client: httpx.AsyncClient) -> httpx.Response:
    answered = await client.post(
        "/login_check",
        params={"_username": USER_IDENTIFIER, "_password": USER_PASSWORD},
    )
    assert answered.status_code == 302, answered.text
    return answered


async def _id_token_claims(client: httpx.AsyncClient, code: str) -> Mapping[str, object]:
    answered = await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": VERIFIER,
        },
    )
    assert answered.status_code == 200, answered.text
    return claims_of(text_field(json_of(answered), "id_token"))


def _seconds(clock: MockClock) -> int:
    return int(clock.now().timestamp())


def _refused_with(answered: httpx.Response) -> tuple[str, str]:
    """Return the error and the state a refusal sent the browser back to the client with."""
    assert answered.headers["location"].startswith(f"{REDIRECT_URI}?")
    sent = redirected_with(answered)
    return sent["error"], sent["state"]


def _returned_to(answered: httpx.Response) -> tuple[str, Mapping[str, str]]:
    """Return the path a redirect sends the browser to, and the query it carries."""
    assert answered.status_code == 302, answered.text
    location = urlsplit(answered.headers["location"])
    return location.path, dict(parse_qsl(location.query))


async def _relogin_round_trip(client: httpx.AsyncClient, **extra: str) -> httpx.Response:
    """Ask for ``extra``, sign in at the login page, follow the way back, and return its answer."""
    sent = await _authorize(client, **extra)
    assert sent.status_code == 302
    assert sent.headers["location"] == _LOGIN_PATH
    back = (await _log_in(client)).headers["location"]
    return await client.get(back)


async def test_prompt_none_with_nobody_signed_in_is_refused_at_the_redirect_uri(
    client: httpx.AsyncClient,
) -> None:
    answered = await _authorize(client, prompt="none")

    assert _refused_with(answered) == ("login_required", _STATE)


async def test_prompt_none_beside_another_value_is_an_invalid_request(
    client: httpx.AsyncClient,
) -> None:
    answered = await _authorize(client, prompt="none login")

    assert answered.status_code == 400
    assert "location" not in answered.headers
    assert json_of(answered)["error"] == "invalid_request"


async def test_prompt_none_with_the_end_user_signed_in_goes_on_to_the_code(
    client: httpx.AsyncClient,
) -> None:
    _ = await _log_in(client)

    answered = await _authorize(client, prompt="none")

    assert "code" in redirected_with(answered)


async def test_prompt_none_needing_a_consent_never_given_is_refused_at_the_redirect_uri(
    client: httpx.AsyncClient,
) -> None:
    # The sign-in forbids showing a page, and the deployment's listener has no
    # consent to go on: it raises ``consent_required``, which the endpoint
    # delivers to the client like any other refusal.
    _ = await _log_in(client)

    answered = await _authorize(client, client_id=CONSENT_CLIENT_ID, prompt="none")

    assert _refused_with(answered) == ("consent_required", _STATE)


async def test_prompt_consent_reaches_the_listener_as_the_value_it_named(
    client: httpx.AsyncClient,
) -> None:
    # The listener reads it through the request's own ``get_prompt()`` and
    # names it back on the page it answers with.
    _ = await _log_in(client)

    answered = await _authorize(client, client_id=CONSENT_CLIENT_ID, prompt="consent")

    assert answered.status_code == 200
    assert answered.text == f"{CONSENT_PAGE} prompt=consent"


async def test_prompt_login_sends_a_signed_in_end_user_to_sign_in_again(
    client: httpx.AsyncClient,
) -> None:
    _ = await _log_in(client)

    answered = await _authorize(client, prompt="login")

    assert answered.status_code == 302
    assert answered.headers["location"] == _LOGIN_PATH


async def test_the_way_back_from_the_login_page_no_longer_asks_for_a_login(
    client: httpx.AsyncClient,
) -> None:
    _ = await _log_in(client)
    _ = await _authorize(client, prompt="login consent")

    path, query = _returned_to(await _log_in(client))

    assert path == "/authorize"
    assert query == {**_query(), "prompt": "consent"}


async def test_prompt_login_ends_in_a_code_once_the_end_user_signed_in_again(
    client: httpx.AsyncClient,
) -> None:
    _ = await _log_in(client)

    answered = await _relogin_round_trip(client, prompt="login")

    assert redirected_with(answered)["state"] == _STATE
    assert "code" in redirected_with(answered)


async def test_a_sign_in_older_than_max_age_is_made_again(
    client: httpx.AsyncClient,
    clock: MockClock,
) -> None:
    _ = await _log_in(client)
    clock.sleep(10 * _MINUTE)

    answered = await _relogin_round_trip(client, max_age="60")
    signed_in_again_at = _seconds(clock)

    auth_time = (await _id_token_claims(client, redirected_with(answered)["code"]))["auth_time"]
    assert isinstance(auth_time, int)
    assert abs(auth_time - signed_in_again_at) <= 5


async def test_a_sign_in_within_max_age_goes_straight_on_to_the_code(
    client: httpx.AsyncClient,
    clock: MockClock,
) -> None:
    _ = await _log_in(client)
    clock.sleep(_MINUTE)

    answered = await _authorize(client, max_age="600")

    assert "code" in redirected_with(answered)


async def test_prompt_none_with_a_sign_in_older_than_max_age_is_refused(
    client: httpx.AsyncClient,
    clock: MockClock,
) -> None:
    _ = await _log_in(client)
    clock.sleep(10 * _MINUTE)

    answered = await _authorize(client, prompt="none", max_age="60")

    assert _refused_with(answered) == ("login_required", _STATE)


async def test_an_unregistered_redirect_uri_is_refused_as_a_document_never_a_redirect(
    client: httpx.AsyncClient,
) -> None:
    answered = await client.get(
        "/authorize",
        params=_query(prompt="none", redirect_uri="https://attacker.test/steal"),
    )

    assert "location" not in answered.headers
    assert answered.status_code in {400, 401}
    assert "error" in json_of(answered)


async def test_a_request_asking_nothing_of_the_sign_in_is_left_to_the_endpoint(
    client: httpx.AsyncClient,
) -> None:
    _ = await _log_in(client)

    answered = await _authorize(client)

    assert "code" in redirected_with(answered)


async def test_a_firewall_keeping_no_session_is_refused_by_name() -> None:
    app = served_application(openid_kernel(STATELESS_PROMPT_ENV))

    async with serving(app) as client:
        with pytest.raises(InvalidConfigurationError, match="stateless") as raised:
            _ = await _authorize(client, prompt="login")

    assert '"api"' in str(raised.value)
