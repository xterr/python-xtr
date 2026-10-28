"""Keys and tokens for the OIDC token-handler tests.

Everything here is in-memory: the keys are generated with joserfc and the
tokens signed with them — no network, no clock but the one the tests inject.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
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
