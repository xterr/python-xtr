"""The key material and token minting the served OIDC fixture verifies against.

A key is generated once at import; its public half is the JWKS the OIDC firewall
pins, and ``mint`` signs tokens with its private half at the real wall clock the
handler reads, so a freshly minted token is valid now.
"""

from __future__ import annotations

import json
import time

from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

__all__ = ["AUDIENCE", "ISSUER", "PUBLIC_JWKS", "mint"]

ISSUER = "https://issuer.example"
AUDIENCE = "shop-api"

_KEY = RSAKey.generate_key(2048, parameters={"kid": "fixture-1"})
PUBLIC_JWKS = json.dumps(KeySet([_KEY]).as_dict(private=False))


def mint(*, subject: str = "alice", audience: str = AUDIENCE, issuer: str = ISSUER) -> str:
    """Sign a token valid for the next hour for ``subject``."""
    now = int(time.time())
    return jwt.encode(
        {"alg": "RS256", "kid": "fixture-1", "typ": "at+jwt"},
        {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "iat": now,
            "nbf": now,
            "exp": now + 3600,
            "scope": "books:read",
        },
        _KEY,
    )
