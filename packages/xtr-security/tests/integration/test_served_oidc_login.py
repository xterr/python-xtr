"""An OIDC login over a real served application, its provider answered from memory.

Drives the served OIDC login fixture through ``httpx.ASGITransport`` inside the
app's lifespan — never ``TestClient`` — with the firewall's HTTP client, the one
service every request to the provider goes through, replaced by a script that
answers as the provider: its discovery document, and its token endpoint, whose
ID token repeats the nonce the authorization request carried. The browser keeps
the session cookie between requests; following a redirect to the provider is
the test's to do, as it is a browser's.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, final
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import OctKey
from xtr_clock import SystemClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_kernel.testing import override_services

from tests.fixtures.oidc_login_app.app import app
from tests.fixtures.oidc_login_app.config import CLIENT_ID, FAILURE_PATH, ISSUER

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_http_client_contracts import RequestOptions

pytestmark = pytest.mark.anyio

#: Where the fixture is served.
_ORIGIN: Final = "http://test"

#: How long an ID token the provider mints stays valid, in seconds.
_ID_TOKEN_LIFETIME: Final = 300

_DISCOVERY_URL: Final = f"{ISSUER}/.well-known/openid-configuration"
_TOKEN_URL: Final = f"{ISSUER}/token"

#: The provider's discovery document: the endpoints a sign-in reaches.
_DOCUMENT: Final = {
    "issuer": ISSUER,
    "authorization_endpoint": f"{ISSUER}/authorize",
    "token_endpoint": _TOKEN_URL,
    "jwks_uri": f"{ISSUER}/jwks",
}


@final
class _Provider:
    """Answers as the login's provider: its discovery document, and its token endpoint.

    A code is issued for the nonce a browser's authorization request carried,
    and redeemed for an ID token naming alice that repeats it.
    """

    def __init__(self) -> None:
        self._nonces: dict[str, str] = {}
        self._key = OctKey.generate_key(256)

    def issue_code(self, nonce: str) -> str:
        """Approve the sign-in that sent ``nonce``, and return the code it is redeemed with."""
        code = f"code-{len(self._nonces)}"
        self._nonces[code] = nonce
        return code

    def answer(self, method: str, url: str, options: RequestOptions) -> MockResponse:
        """Answer what the login asks of the provider."""
        if url == _DISCOVERY_URL:
            return _json(_DOCUMENT)
        body = options.get("body")
        assert (method, url) == ("POST", _TOKEN_URL)
        assert isinstance(body, Mapping)
        return _json(
            {
                "access_token": "an-access-token",
                "token_type": "Bearer",
                "id_token": self._id_token(self._nonces[str(body["code"])]),
            }
        )

    def _id_token(self, nonce: str) -> str:
        """Return an ID token naming alice for this client, repeating ``nonce``."""
        now = int(SystemClock().now().timestamp())
        claims = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "alice",
            "iat": now,
            "exp": now + _ID_TOKEN_LIFETIME,
            "nonce": nonce,
        }
        return jwt.encode({"alg": "HS256"}, claims, self._key)


def _json(document: Mapping[str, object]) -> MockResponse:
    """Return ``document`` as the provider's JSON answer."""
    return MockResponse(
        json.dumps(document).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


@pytest.fixture
def provider() -> _Provider:
    """The provider the login signs in with."""
    return _Provider()


@pytest.fixture
async def browser(provider: _Provider) -> AsyncIterator[httpx.AsyncClient]:
    """Serve the fixture over ``provider``, and yield a browser keeping its session cookie."""
    with override_services(
        app, {(HttpClientInterface, "main#oidc_http_client"): MockHttpClient(provider.answer)}
    ):
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url=_ORIGIN) as opened:
                yield opened


def _asked_of_the_provider(sent: httpx.Response) -> dict[str, str]:
    """Return the parameters of the authorization request ``sent`` redirects to."""
    assert sent.status_code == 302, sent.text
    location = sent.headers["location"]
    assert location.startswith(f"{ISSUER}/authorize?"), location
    return dict(parse_qsl(urlsplit(location).query))


async def test_a_login_started_from_a_denied_page_returns_to_that_page(
    browser: httpx.AsyncClient,
    provider: _Provider,
) -> None:
    asked = _asked_of_the_provider(await browser.get("/account/profile", params={"tab": "1"}))

    landed = await browser.get(
        "/oidc/callback",
        params={"code": provider.issue_code(asked["nonce"]), "state": asked["state"]},
    )

    assert landed.status_code == 302, landed.text
    assert landed.headers["location"] == f"{_ORIGIN}/account/profile?tab=1"


async def test_a_callback_failing_its_state_check_is_sent_to_the_failure_path(
    browser: httpx.AsyncClient,
    provider: _Provider,
) -> None:
    asked = _asked_of_the_provider(await browser.get("/account/profile"))

    refused = await browser.get(
        "/oidc/callback",
        params={"code": provider.issue_code(asked["nonce"]), "state": f"{asked['state']}-tampered"},
    )

    assert refused.status_code == 302, refused.text
    assert refused.headers["location"] == FAILURE_PATH
