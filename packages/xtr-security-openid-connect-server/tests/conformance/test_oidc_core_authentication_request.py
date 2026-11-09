"""OpenID Connect Core 1.0 — the authentication request, and the sign-in it starts.

The first test is a whole sign-in as a client application makes it: the
repository's own OpenID Connect login, on a second application with a kernel
of its own, sends the browser from a page needing a signed-in user to the
served provider, takes it back with a code it redeems, an ID token it verifies
and a userinfo answer it reads, and returns it to that page.

The rest drive the authorization endpoint the way a browser would, in the
deployment each requirement is about: one signing the end-user in with a form,
whose firewall lists the provider's prompt step, for ``prompt`` and
``max_age``; the plain deployment otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import pytest
from xtr_clock import Clock, MockClock
from xtr_http_kernel.testing import override_services

from tests.fixtures.openid_app.config import (
    PROMPT_ENV,
    USER_IDENTIFIER,
    USER_PASSWORD,
    USERINFO_ENV,
)
from tests.fixtures.relying_party_app.config import ACCOUNT_PATH
from tests.support.relying_party_login import CLIENT_ORIGIN, browsing
from tests.support.served import (
    REDIRECT_URI,
    claims_of,
    json_of,
    openid_kernel,
    redirected_with,
    served_application,
    serving,
    text_field,
)
from tests.support.sign_in import (
    STATE,
    authorization_query,
    authorize,
    owner_token,
    redeem,
    signed_in,
)
from tests.support.signing import ISSUER

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    import httpx

pytestmark = pytest.mark.anyio

_LOGIN_PATH: Final = "/login"
_MINUTE: Final = 60


@pytest.fixture
def clock() -> MockClock:
    # Frozen at the current instant, so whatever reads the system clock rather
    # than the application's agrees with it until a test moves it.
    return MockClock()


@pytest.fixture
async def browser(clock: MockClock) -> AsyncGenerator[httpx.AsyncClient]:
    """A browser on the deployment signing the end-user in with a form."""
    app = served_application(openid_kernel(PROMPT_ENV))
    with override_services(app, {Clock: Clock(clock)}):
        async with serving(app) as served:
            yield served


async def _ask(browser: httpx.AsyncClient, **extra: str) -> httpx.Response:
    """Send the authentication request from the browser, carrying no token of its own."""
    return await browser.get("/authorize", params=authorization_query(**extra))


async def _log_in(browser: httpx.AsyncClient) -> httpx.Response:
    answered = await browser.post(
        "/login_check",
        params={"_username": USER_IDENTIFIER, "_password": USER_PASSWORD},
    )
    assert answered.status_code == 302, answered.text
    return answered


async def _id_token_claims(
    browser: httpx.AsyncClient, answered: httpx.Response
) -> Mapping[str, object]:
    """Redeem the code ``answered`` carries and return what its ID token claims."""
    redeemed = await redeem(browser, redirected_with(answered)["code"])
    assert redeemed.status_code == 200, redeemed.text
    return claims_of(text_field(json_of(redeemed), "id_token"))


def _refused_with(answered: httpx.Response) -> tuple[str, str]:
    """Return the error and the state a refusal sent the browser back to the client with."""
    assert answered.headers["location"].startswith(f"{REDIRECT_URI}?")
    sent = redirected_with(answered)
    return sent["error"], sent["state"]


def _path_and_query(location: str) -> str:
    """Return the part of ``location`` an application serving its origin routes on."""
    target = urlsplit(location)
    return f"{target.path}?{target.query}"


# Section 3.1 — Authentication using the Authorization Code Flow, end to end


async def test_a_client_application_signs_its_user_in_with_the_provider() -> None:
    provider_app = served_application(openid_kernel(USERINFO_ENV))
    async with serving(provider_app) as provider, browsing(provider) as browser:
        # A page of the client's needs a signed-in user, so the client sends
        # the browser to the provider's authorization endpoint.
        sent = await browser.get(ACCOUNT_PATH, params={"tab": "1"})
        assert sent.status_code == 302, sent.text
        authorization = sent.headers["location"]
        assert authorization.startswith(f"{ISSUER}/authorize?")
        asked = dict(parse_qsl(urlsplit(authorization).query))
        assert {"state", "nonce", "code_challenge"} <= set(asked)
        assert "openid" in asked["scope"].split(" ")

        # The end-user is signed in at the provider, which sends them back.
        back = await provider.get(
            _path_and_query(authorization),
            headers={"Authorization": f"Bearer {await owner_token(provider)}"},
        )
        assert back.status_code == 302, back.text
        assert back.headers["location"].startswith(f"{REDIRECT_URI}?")

        # The client redeems the code, verifies the ID token, reads userinfo,
        # and returns the browser to the page it asked for.
        landed = await browser.get(_path_and_query(back.headers["location"]))
        assert landed.status_code == 302, landed.text
        assert landed.headers["location"] == f"{CLIENT_ORIGIN}{ACCOUNT_PATH}?tab=1"
        page = await browser.get(_path_and_query(landed.headers["location"]))

    assert page.status_code == 200, page.text
    assert json_of(page) == {"user": USER_IDENTIFIER}


# Section 3.1.2.1 — Authentication Request


async def test_the_authorization_endpoint_answers_a_get() -> None:
    # "Authorization Servers MUST support the use of the HTTP GET and POST
    # methods defined in RFC 7231 at the Authorization Endpoint."
    async with serving(served_application(openid_kernel())) as client:
        answered = await authorize(client)

    assert "code" in redirected_with(answered)


async def test_the_authorization_endpoint_answers_a_posted_form() -> None:
    # "If using the HTTP POST method, the request parameters are serialized
    # using Form Serialization."
    async with serving(served_application(openid_kernel())) as client:
        answered = await client.post(
            "/authorize",
            data=authorization_query(),
            headers={"Authorization": f"Bearer {await owner_token(client)}"},
        )

    assert "code" in redirected_with(answered)


async def test_a_request_naming_no_redirect_uri_is_refused() -> None:
    # "redirect_uri REQUIRED."
    query = {name: value for name, value in authorization_query().items() if name != "redirect_uri"}
    async with serving(served_application(openid_kernel())) as client:
        answered = await client.get(
            "/authorize",
            params=query,
            headers={"Authorization": f"Bearer {await owner_token(client)}"},
        )

    assert answered.status_code == 400


async def test_parameters_asking_for_a_presentation_are_ignored_without_error() -> None:
    # Section 15.1: OPs MUST support ``display``, ``ui_locales`` and
    # ``acr_values``, where "the minimum level of support required for this
    # parameter is simply that its use must not result in an error".
    async with serving(served_application(openid_kernel())) as client:
        answered = await authorize(client, display="popup", ui_locales="fr-CA fr", acr_values="1")

    assert "code" in redirected_with(answered)


async def test_prompt_none_with_nobody_signed_in_is_refused_at_the_redirect_uri(
    browser: httpx.AsyncClient,
) -> None:
    # "none: The Authorization Server MUST NOT display any authentication or
    # consent user interface pages. An error is returned if an End-User is not
    # already authenticated"; Section 3.1.2.6 names it login_required.
    answered = await _ask(browser, prompt="none")

    assert _refused_with(answered) == ("login_required", STATE)


async def test_prompt_none_with_the_end_user_signed_in_goes_on_to_the_code(
    browser: httpx.AsyncClient,
) -> None:
    _ = await _log_in(browser)

    answered = await _ask(browser, prompt="none")

    assert redirected_with(answered)["state"] == STATE
    assert "code" in redirected_with(answered)


async def test_prompt_none_beside_another_value_is_refused(browser: httpx.AsyncClient) -> None:
    # "If this parameter contains none with any other value, an error is
    # returned." Answered as a document — a deliberate deviation, recorded.
    answered = await _ask(browser, prompt="none login")

    assert answered.status_code == 400
    assert "location" not in answered.headers
    assert json_of(answered)["error"] == "invalid_request"


async def test_prompt_login_has_a_signed_in_end_user_sign_in_again(
    browser: httpx.AsyncClient,
    clock: MockClock,
) -> None:
    # "login: The Authorization Server SHOULD prompt the End-User for
    # reauthentication."
    _ = await _log_in(browser)
    clock.sleep(_MINUTE)

    sent = await _ask(browser, prompt="login")
    assert (sent.status_code, sent.headers["location"]) == (302, _LOGIN_PATH)
    signed_in_again_at = int(clock.now().timestamp())
    answered = await browser.get((await _log_in(browser)).headers["location"])

    assert (await _id_token_claims(browser, answered))["auth_time"] == signed_in_again_at


async def test_prompt_none_posted_as_a_form_is_decided_as_a_get_is(
    browser: httpx.AsyncClient,
) -> None:
    answered = await browser.post("/authorize", data=authorization_query(prompt="none"))

    assert _refused_with(answered) == ("login_required", STATE)


async def test_prompt_login_posted_as_a_form_returns_to_the_request_after_sign_in(
    browser: httpx.AsyncClient,
    clock: MockClock,
) -> None:
    # The request waiting in the session is the one the form posted: the
    # end-user comes back to it, without login, and goes on to the code.
    _ = await _log_in(browser)
    clock.sleep(_MINUTE)

    sent = await browser.post("/authorize", data=authorization_query(prompt="login"))
    assert (sent.status_code, sent.headers["location"]) == (302, _LOGIN_PATH)
    signed_in_again_at = int(clock.now().timestamp())
    answered = await browser.get((await _log_in(browser)).headers["location"])

    assert redirected_with(answered)["state"] == STATE
    assert (await _id_token_claims(browser, answered))["auth_time"] == signed_in_again_at


async def test_prompt_select_account_is_refused(browser: httpx.AsyncClient) -> None:
    # Outside what this provider acts on: refused rather than ignored, a
    # deliberate deviation, recorded.
    _ = await _log_in(browser)

    answered = await _ask(browser, prompt="select_account")

    assert answered.status_code == 400
    assert json_of(answered)["error"] == "invalid_request"


async def test_max_age_has_the_id_token_state_when_the_end_user_signed_in(
    browser: httpx.AsyncClient,
    clock: MockClock,
) -> None:
    # "When max_age is used, the ID Token returned MUST include an auth_time
    # Claim Value."
    _ = await _log_in(browser)
    logged_in_at = int(clock.now().timestamp())
    clock.sleep(_MINUTE)

    answered = await _ask(browser, max_age="600")

    assert (await _id_token_claims(browser, answered))["auth_time"] == logged_in_at


async def test_a_sign_in_older_than_max_age_is_made_again(
    browser: httpx.AsyncClient,
    clock: MockClock,
) -> None:
    # "If the elapsed time is greater than this value, the OP MUST attempt to
    # actively re-authenticate the End-User."
    _ = await _log_in(browser)
    clock.sleep(10 * _MINUTE)

    sent = await _ask(browser, max_age="60")
    assert (sent.status_code, sent.headers["location"]) == (302, _LOGIN_PATH)
    signed_in_again_at = int(clock.now().timestamp())
    answered = await browser.get((await _log_in(browser)).headers["location"])

    assert (await _id_token_claims(browser, answered))["auth_time"] == signed_in_again_at


# Section 3.1.2.6 — Authentication Error Response


async def test_a_refusal_about_the_redirect_uri_is_never_a_redirect(
    browser: httpx.AsyncClient,
) -> None:
    # "Unless the Redirection URI is invalid, the Authorization Server returns
    # the Client to the Redirection URI specified in the Authorization
    # Request with the appropriate error and state parameters."
    answered = await _ask(browser, prompt="none", redirect_uri="https://attacker.test/steal")

    assert "location" not in answered.headers
    assert "error" in json_of(answered)


# Section 3.1.3.2 — Token Request Validation


async def test_a_code_issued_for_a_request_without_openid_earns_no_id_token() -> None:
    # "Verify that the Authorization Code used was issued in response to an
    # OpenID Connect Authentication Request (so that an ID Token will be
    # returned from the Token Endpoint)."
    async with serving(served_application(openid_kernel())) as client:
        issued = await signed_in(client, scope="read")

    assert "access_token" in issued
    assert "id_token" not in issued
