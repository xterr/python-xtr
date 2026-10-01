"""Keys, tokens and an in-process issuer for the OIDC token-handler tests.

Everything here is in-memory: the keys are generated with joserfc, the tokens
signed with them, and the JWKS and discovery documents served by a tiny ASGI
app reached through :class:`httpx.ASGITransport` — no network, no clock but the
one the tests inject.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast, final

import httpx
from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from starlette.types import Receive, Scope, Send

__all__ = [
    "IssuerServer",
    "make_key",
    "make_key_set",
    "mint",
    "public_jwks",
]

ISSUER = "https://issuer.example"
AUDIENCE = "shop-api"
NOW = 1_000_000


def make_key(kid: str = "k1") -> RSAKey:
    """Generate an RSA key carrying ``kid``."""
    return RSAKey.generate_key(2048, parameters={"kid": kid})


def make_key_set(*keys: RSAKey) -> KeySet:
    """Gather ``keys`` into a joserfc key set."""
    return KeySet(list(keys))


def public_jwks(*keys: RSAKey) -> str:
    """Return the public JWKS document for ``keys`` as a JSON string."""
    return json.dumps(KeySet(list(keys)).as_dict(private=False))


def mint(  # noqa: PLR0913 -- a token has many claims, each optional
    key: RSAKey,
    *,
    issuer: str = ISSUER,
    audience: str | list[str] = AUDIENCE,
    subject: str = "alice",
    now: int = NOW,
    ttl: int = 3600,
    nbf_offset: int = 0,
    typ: str | None = None,
    include_exp: bool = True,
    extra: Mapping[str, object] | None = None,
) -> str:
    """Sign a token for ``key`` with the given claims and optional ``typ`` header."""
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": now,
        "nbf": now + nbf_offset,
    }
    if include_exp:
        claims["exp"] = now + ttl
    if extra is not None:
        claims.update(extra)
    header: dict[str, object] = {"alg": "RS256", "kid": key.kid}
    if typ is not None:
        header["typ"] = typ
    return jwt.encode(header, claims, key)


@final
class IssuerServer:
    """A tiny ASGI issuer serving discovery and JWKS from in-memory keys.

    Reached through :class:`httpx.ASGITransport`, so a
    :class:`~...DiscoveryOidcKeySetProvider` pointed at ``base_uri`` or
    ``jwks_uri`` fetches from it without a socket. Every request is counted, so
    a test can assert one fetch where it expects one.
    """

    _keys: KeySet
    _base_uri: str
    _omit_jwks_uri: bool
    _jwks_body: object | None
    jwks_requests: int
    discovery_requests: int
    down: bool

    def __init__(
        self,
        keys: KeySet,
        *,
        base_uri: str = "https://issuer.example",
        omit_jwks_uri: bool = False,
        jwks_body: object | None = None,
    ) -> None:
        """Serve ``keys`` as the JWKS the discovery document at ``base_uri`` names.

        With ``omit_jwks_uri`` the discovery document names no ``jwks_uri``, as a
        broken issuer would, so a provider pointed at it fails to discover. With
        ``jwks_body`` the JWKS path serves that raw value instead of the keys — a
        malformed set, or a body that is not even an object — so a provider fails
        to read it.
        """
        self._keys = keys
        self._base_uri = base_uri.rstrip("/")
        self._omit_jwks_uri = omit_jwks_uri
        self._jwks_body = jwks_body
        self.jwks_requests = 0
        self.discovery_requests = 0
        self.down = False

    @property
    def base_uri(self) -> str:
        """Return the issuer's base URI."""
        return self._base_uri

    @property
    def jwks_uri(self) -> str:
        """Return the URI the JWKS is served at."""
        return f"{self._base_uri}/jwks.json"

    def client_factory(self) -> Callable[[], httpx.AsyncClient]:
        """Return a factory building a client that reaches this issuer over ASGI."""
        transport = httpx.ASGITransport(self._app)

        def build() -> httpx.AsyncClient:
            return httpx.AsyncClient(transport=transport)

        return build

    async def _app(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Answer the discovery and JWKS paths, and 404 anything else."""
        del receive
        path = cast("str", scope["path"])
        if path == "/.well-known/openid-configuration":
            self.discovery_requests += 1
            document: dict[str, object] = {"issuer": self._base_uri}
            if not self._omit_jwks_uri:
                document["jwks_uri"] = self.jwks_uri
            await _json(send, document)
            return
        if path == "/jwks.json":
            self.jwks_requests += 1
            if self.down:
                await _json(send, {"error": "unavailable"}, status=503)
                return
            body = (
                self._jwks_body
                if self._jwks_body is not None
                else self._keys.as_dict(
                    private=False,
                )
            )
            await _json(send, body)
            return
        await _json(send, {"error": "not found"}, status=404)


async def _json(send: Send, body: object, *, status: int = 200) -> None:
    """Send ``body`` as a JSON response with ``status``."""
    payload = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        },
    )
    await send({"type": "http.response.body", "body": payload})
