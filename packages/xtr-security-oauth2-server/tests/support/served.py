"""Driving this package's endpoints through a real served application.

Nothing here is a double: a kernel builds the container, ``setup`` mounts the
routes this package contributes on a real application, and a client drives it over ASGI. What a
test asserts on is what a client would receive.

The readers return settled types rather than whatever the wire decoded, so that
a test asserting on a field says what it expects the field to be.
"""

from __future__ import annotations

import base64
import hashlib
import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Final, cast

import httpx
from fastapi import FastAPI
from xtr_dependency_injection import Injected, Kernel, Target
from xtr_http_kernel.setup import setup
from xtr_password_hasher import PasswordHasherInterface

from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Mapping, Sequence

__all__ = [
    "CLIENT_ID",
    "CLIENT_SECRET",
    "REDIRECT_URI",
    "SCOPE",
    "SEED_PATH",
    "claims_of",
    "client_credentials_token",
    "code_challenge_of",
    "header_of",
    "int_field",
    "json_of",
    "oauth2_kernel",
    "seed_any_grant_client",
    "served_application",
    "serving",
    "text_field",
    "text_fields",
]

#: The client every served test registers, unless it registers one of its own.
CLIENT_ID: Final = "a-confidential-client"

#: Its secret, as a client would send it. Never stored this way: the seeding
#: endpoint hashes it, the way an administration screen would.
CLIENT_SECRET: Final = "the-plaintext-secret"

#: The one scope the seeded client is registered for.
SCOPE: Final = "read"

#: Where a seeded client may be sent back to, when it is registered with one.
REDIRECT_URI: Final = "https://client.test/callback"

#: Where the seeding endpoint lives. It stands where an administration screen
#: or the create-client command would.
SEED_PATH: Final = "/seed-client"


def oauth2_kernel(
    app_module: str = "tests.fixtures.oauth2_server_app",
    routes_module: str | None = "tests.support.default_routes",
) -> Kernel:
    """Return a kernel of ``app_module``, running this package's bundle.

    ``routes_module`` is scanned beside the application and carries the routes
    file registering this server's endpoints — routing is never imported
    automatically, so a served application always has one. An application
    arranging its own passes ``None`` and brings its own routes file.
    """
    return Kernel(
        app_module,
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
        concurrent_scoped_access=True,
        resources=(app_module,) if routes_module is None else (app_module, routes_module),
    )


def served_application(
    kernel: Kernel | None = None,
    extend: Callable[[FastAPI], None] | None = None,
) -> FastAPI:
    """Return an application serving this package's endpoints, plus a way to seed a client.

    The seeding endpoint is the only way a test registers a client without
    reaching past the container's public surface, and it proves the ordinary
    injection markers reach this package's services from an application's own
    route.

    ``extend`` registers an application's own routes — an API behind a firewall,
    say — before serving begins, since an application refuses middleware once it
    has started.

    The firewalls the fixture configurations match run as the firewall — a
    subscriber over the kernel lifecycle's events — so the routes this
    package contributes carry no firewall dependency of their own: the
    ``login`` firewall a fixture configures establishes the resource owner on
    the authorization endpoint, and the token endpoint — where authenticating
    the *client* is the authorization server's own job — stays outside it.
    """
    app = FastAPI()

    @app.post(SEED_PATH)
    async def seed_client(
        clients: Injected[ClientManagerInterface],
        hasher: Annotated[PasswordHasherInterface, Target("oauth2_server")],
        *,
        identifier: str = CLIENT_ID,
        secret: str = CLIENT_SECRET,
        grant: str = "client_credentials",
        redirect_uri: str = "",
        scope: str = SCOPE,
        plain_pkce: bool = False,
    ) -> dict[str, str]:
        # An empty secret registers a public client, which is what the
        # proof-key requirement is about.
        client = Client("A client", identifier, hasher.hash(secret) if secret else None)
        # An empty grant leaves the registration naming none, and a client
        # with no grants may use any — the rule a test relies on when one
        # client has to drive two flows.
        if grant:
            _ = client.set_grants(Grant(grant))
        if redirect_uri:
            _ = client.set_redirect_uris(RedirectUri(redirect_uri))
        # Whether this client may send the verifier unhashed, which only a
        # registration may say.
        _ = client.set_allow_plain_text_pkce(plain_pkce)
        # A registration naming several scopes is what a token carrying
        # several is issued against; one is the usual case, so it is the
        # default.
        _ = client.set_scopes(*(Scope(name) for name in scope.split(" ") if name))
        await clients.save(client)

        return {"client_id": identifier}

    if extend is not None:
        extend(app)
    # Routes first: an application refuses middleware once it has started.
    setup(app, kernel if kernel is not None else oauth2_kernel())

    return app


@asynccontextmanager
async def serving(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient]:
    """Serve ``app`` for one application life and yield a client driving it."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://served.test",
        ) as client:
            yield client


def json_of(response: httpx.Response) -> Mapping[str, object]:
    """Return the JSON document ``response`` carries."""
    return cast("Mapping[str, object]", response.json())


def text_field(document: Mapping[str, object], name: str) -> str:
    """Return the ``name`` field of ``document``, which must be a string."""
    value = document[name]
    assert isinstance(value, str), f"{name} is {value!r}, not a string"

    return value


def int_field(document: Mapping[str, object], name: str) -> int:
    """Return the ``name`` field of ``document``, which must be a whole number."""
    value = document[name]
    assert isinstance(value, int), f"{name} is {value!r}, not a whole number"

    return value


def text_fields(document: Mapping[str, object], name: str) -> Sequence[str]:
    """Return the ``name`` field of ``document``, which must be a list of strings."""
    value = document[name]
    assert isinstance(value, list), f"{name} is {value!r}, not a list"
    # What a decoded list holds cannot be known from its type, so every
    # element is checked rather than trusted.
    items = cast("Sequence[object]", value)
    for item in items:
        assert isinstance(item, str), f"{name} holds {item!r}, which is not a string"

    return cast("Sequence[str]", items)


def _segment(token: str, index: int) -> Mapping[str, object]:
    """Return one decoded segment of a compact token, without verifying it.

    A test reads what was signed rather than re-deriving it, so that what it
    asserts on is what a resource server would see.
    """
    encoded = token.split(".")[index]
    padded = encoded + "=" * (-len(encoded) % 4)

    return cast("Mapping[str, object]", json.loads(base64.urlsafe_b64decode(padded)))


def header_of(token: str) -> Mapping[str, object]:
    """Return the header a compact token carries."""
    return _segment(token, 0)


def claims_of(token: str) -> Mapping[str, object]:
    """Return the claims a compact token carries."""
    return _segment(token, 1)


async def client_credentials_token(
    client: httpx.AsyncClient,
    scope: str | None = None,
) -> str:
    """Seed a client, have it authenticate as itself, and return the access token."""
    _ = await client.post(SEED_PATH)
    form = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    if scope is not None:
        form["scope"] = scope
    issued = json_of(await client.post("/token", data=form))

    return text_field(issued, "access_token")


async def seed_any_grant_client(client: httpx.AsyncClient) -> None:
    """Register a client naming no grant, so one registration drives two flows.

    A client with no grants may use any, which is the rule a test relies on
    when the same client has to exchange a password and then a refresh token.
    """
    _ = await client.post(SEED_PATH, params={"grant": ""})


def code_challenge_of(verifier: str) -> str:
    """Return the S256 challenge a client derives from ``verifier``.

    What the hashed method is for: the challenge travels in the authorization
    request, where every hop can see it, and only the holder of the verifier
    can redeem the code it guards.
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()

    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
