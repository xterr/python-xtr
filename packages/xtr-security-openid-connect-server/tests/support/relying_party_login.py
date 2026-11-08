"""A second application, signing its users in with the served provider.

The provider is checked here by the repository's own OpenID Connect login — the
authenticator a client application lists on its firewall — rather than by a
test reading answers. Two kernels run side by side: the provider's, served as
the tests always serve it, and the client application's, built from its own
fixture. A browser is driven between them by hand, since that is all a browser
does: follow redirects from one to the other.

The login reaches the provider through a client that hands every request to
the provider's application over ASGI, live, so the code it exchanges is the
one the provider just issued and the token it verifies is the one it just
signed. Only the readers that would open a network connection — the discovery
reader, the protocol client and the signature verifier — are swapped for ones
built over that client; the authenticator, its session, its ``state``, its
``nonce`` and its checks are the application's own.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Final
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI
from xtr_cache import ArrayAdapter
from xtr_dependency_injection import Kernel
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_http_kernel.setup import setup
from xtr_http_kernel.testing import override_services
from xtr_security.bundle import SecurityBundle
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser
from xtr_security_http.oauth2.client_authentication import NoClientAuthentication
from xtr_security_http.oidc import OidcClient, OidcDiscovery, OidcSignatureVerifier

from tests.fixtures.openid_app.config import ALGORITHM
from tests.fixtures.relying_party_app.config import FIREWALL, HOME_PATH
from tests.support.served import CLIENT_ID
from tests.support.signing import ISSUER

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Hashable

    from xtr_http_client_contracts import RequestOptions

__all__ = ["CLIENT_ORIGIN", "browsing", "forwarding_client", "login_services"]

#: Where the client application is served: the origin of the redirect URI the
#: provider has registered for it.
CLIENT_ORIGIN: Final = "https://client.test"

_APP_MODULE: Final = "tests.fixtures.relying_party_app"


def forwarding_client(provider: httpx.AsyncClient) -> MockHttpClient:
    """Return a client handing every request to the provider ``provider`` reaches.

    The path and query of each URL are kept and its origin dropped, so a
    request for an endpoint under the issuer reaches the provider's own route.
    A form body travels as a form and a bearer token as the ``Authorization``
    header — the two ways the login sends anything.
    """

    async def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
        target = urlsplit(url)
        path = f"{target.path}?{target.query}" if target.query else target.path
        headers: dict[str, str] = {}
        bearer = options.get("auth_bearer")
        if isinstance(bearer, str):
            headers["authorization"] = f"Bearer {bearer}"
        body = options.get("body")
        form = (
            {name: str(value) for name, value in body.items()}
            if isinstance(body, Mapping)
            else None
        )
        answered = await provider.request(method, path, data=form, headers=headers)

        return MockResponse(
            answered.content,
            {"http_code": answered.status_code, "response_headers": dict(answered.headers)},
        )

    return MockHttpClient(answer, base_uri=ISSUER)


def login_services(
    provider: httpx.AsyncClient,
) -> Mapping[type | tuple[type, Hashable], object]:
    """Return the services the login is served with, reaching ``provider``.

    The network readers are keyed as the security bundle registers them for
    the firewall, so each replaces the reader that would otherwise open a
    connection to the issuer. The signature verifier keeps its default, strict
    key usage: only keys the provider marked for signatures verify anything.
    """
    client = forwarding_client(provider)
    discovery = OidcDiscovery(client, ArrayAdapter(), issuer=ISSUER)

    return {
        (OidcDiscovery, f"{FIREWALL}#oidc_discovery"): discovery,
        (OidcClient, f"{FIREWALL}#oidc_client"): OidcClient(
            client,
            discovery,
            CLIENT_ID,
            NoClientAuthentication(),
        ),
        (OidcSignatureVerifier, f"{FIREWALL}#oidc_signature_verifier"): OidcSignatureVerifier(
            discovery,
            ArrayAdapter(),
            client,
            algorithms=(ALGORITHM,),
        ),
    }


def _client_application() -> FastAPI:
    """Return the client application: a home page naming who signed in."""
    app = FastAPI()

    @app.get(HOME_PATH)
    async def home(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, str]:
        return {"user": user.get_user_identifier()}

    kernel = Kernel(
        _APP_MODULE,
        env="test",
        bundles={SecurityBundle: {"all": True}},
        concurrent_scoped_access=True,
    )
    setup(app, kernel)

    return app


@asynccontextmanager
async def browsing(provider: httpx.AsyncClient) -> AsyncGenerator[httpx.AsyncClient]:
    """Serve the client application signing in with ``provider``, and yield a browser on it.

    The browser keeps the application's session cookie between requests, as a
    browser does; following a redirect to the provider is the test's to do.
    """
    app = _client_application()
    with override_services(app, login_services(provider)):
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url=CLIENT_ORIGIN) as browser:
                yield browser
