"""Driving a sign-in through a real served application.

Nothing here is a double: a kernel builds the container with both the
authorization server's bundle and the provider's, ``setup`` mounts the routes
on a real application, and a client drives it over ASGI. What a test asserts on
is what a client would receive.

Every client this seeds is public — it holds no secret — so a sign-in proves
itself with a proof key, as a browser or native application does. Two are
registered identically, and only the deployment's consent listener tells them
apart: its consent was given for one and never for the other.
The one exception is a confidential client registered beside them, naming no
grant, which mints whatever token a test of a reader needs.
"""

from __future__ import annotations

import base64
import hashlib
import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Final, cast
from urllib.parse import parse_qsl, urlsplit

import httpx
from fastapi import FastAPI
from xtr_dependency_injection import Injected, Kernel, Target
from xtr_http_kernel.setup import setup
from xtr_password_hasher import PasswordHasherInterface
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

from xtr_security_openid_connect_server.bundle import OpenIdConnectServerBundle

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

__all__ = [
    "CLIENT_ID",
    "CONSENT_CLIENT_ID",
    "REDIRECT_URI",
    "SCOPE",
    "SERVICE_CLIENT_ID",
    "SERVICE_CLIENT_SECRET",
    "VERIFIER",
    "claims_of",
    "code_challenge_of",
    "header_of",
    "json_of",
    "openid_kernel",
    "redirected_with",
    "served_application",
    "serving",
    "text_field",
]

#: The client every served sign-in is driven as.
CLIENT_ID: Final = "my-client"

#: The client registered beside it that this deployment's consent was never
#: given for, which is how a test reaches the consent listener's own answers.
CONSENT_CLIENT_ID: Final = "my-consent-client"

#: Where both are sent back to.
REDIRECT_URI: Final = "https://client.test/callback"

#: What a sign-in asks for: to sign the user in, and the deployment's own scope.
SCOPE: Final = "openid read"

#: A proof key within the length the standard allows.
VERIFIER: Final = "a-code-verifier-long-enough-for-the-standard"

#: The confidential client seeded beside them. It names no grant, so it may use
#: any, and it is registered for every scope a test of a reader asks for.
SERVICE_CLIENT_ID: Final = "my-service"

#: Its secret, as it sends it; the seeding endpoint stores it hashed.
SERVICE_CLIENT_SECRET: Final = "the-service-secret"

#: The scopes it is registered for. Named, because a client registered for
#: none is handed the deployment's defaults.
_SERVICE_SCOPES: Final = "openid read profile email"

#: The public clients, by the name shown when consent is asked for. Both are
#: registered the same way: a sign-in is driven as either, and only the
#: deployment's consent listener tells them apart.
_PUBLIC_CLIENTS: Final = {CLIENT_ID: "A client", CONSENT_CLIENT_ID: "A client to consent to"}

#: Where the seeding endpoint lives, standing where an administration screen would.
_SEED_PATH: Final = "/seed-client"

_APP_MODULE: Final = "tests.fixtures.openid_app"


def openid_kernel(env: str = "test", routes_module: str | None = None) -> Kernel:
    """Return a kernel of the fixture deployment, served in ``env``.

    ``routes_module`` names a routes file arranging the endpoints in place of
    the deployment's own, which is then not scanned.
    """
    resources = (_APP_MODULE,) if routes_module is None else (_APP_MODULE, routes_module)
    return Kernel(
        _APP_MODULE,
        env=env,
        # The deployment's environments include ones the kernel does not name,
        # where debug would otherwise default to off with a warning.
        debug=True,
        bundles={OAuth2ServerBundle: {"all": True}, OpenIdConnectServerBundle: {"all": True}},
        concurrent_scoped_access=True,
        resources=resources,
        exclude=() if routes_module is None else (f"{_APP_MODULE}.routes",),
    )


def served_application(kernel: Kernel) -> FastAPI:
    """Return an application serving ``kernel``'s endpoints, plus a way to seed the client."""
    app = FastAPI()

    @app.post(_SEED_PATH)
    async def seed_client(
        clients: Injected[ClientManagerInterface],
        hasher: Annotated[PasswordHasherInterface, Target("oauth2_server")],
    ) -> dict[str, str]:
        for identifier, name in _PUBLIC_CLIENTS.items():
            client = Client(name, identifier, None)
            _ = client.set_redirect_uris(RedirectUri(REDIRECT_URI))
            _ = client.set_scopes(*(Scope(scope) for scope in SCOPE.split(" ")))
            await clients.save(client)
        service = Client("A service", SERVICE_CLIENT_ID, hasher.hash(SERVICE_CLIENT_SECRET))
        _ = service.set_scopes(*(Scope(name) for name in _SERVICE_SCOPES.split(" ")))
        await clients.save(service)

        return {"client_id": CLIENT_ID}

    setup(app, kernel)

    return app


@asynccontextmanager
async def serving(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient]:
    """Serve ``app`` for one application life, the client seeded, and yield a client."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://served.test") as client:
            seeded = await client.post(_SEED_PATH)
            assert seeded.status_code == 200, seeded.text
            yield client


def code_challenge_of(verifier: str) -> str:
    """Return the S256 challenge a client derives from ``verifier``."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()

    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def json_of(response: httpx.Response) -> Mapping[str, object]:
    """Return the JSON document ``response`` carries."""
    return cast("Mapping[str, object]", response.json())


def text_field(document: Mapping[str, object], name: str) -> str:
    """Return the ``name`` field of ``document``, which must be a string."""
    value = document[name]
    assert isinstance(value, str), f"{name} is {value!r}, not a string"

    return value


def redirected_with(answered: httpx.Response) -> Mapping[str, str]:
    """Return the parameters a redirect sent the browser back with."""
    assert answered.status_code == 302, f"{answered.status_code}: {answered.text}"

    return dict(parse_qsl(urlsplit(answered.headers["location"]).query))


def _segment(token: str, index: int) -> Mapping[str, object]:
    """Return one decoded segment of a compact token, without verifying it."""
    encoded = token.split(".")[index]
    padded = encoded + "=" * (-len(encoded) % 4)

    return cast("Mapping[str, object]", json.loads(base64.urlsafe_b64decode(padded)))


def header_of(token: str) -> Mapping[str, object]:
    """Return the header a compact token carries."""
    return _segment(token, 0)


def claims_of(token: str) -> Mapping[str, object]:
    """Return the claims a compact token carries."""
    return _segment(token, 1)
