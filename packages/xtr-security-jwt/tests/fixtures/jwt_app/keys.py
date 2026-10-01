"""One signing key the fixture application signs and verifies with."""

from __future__ import annotations

from joserfc.jwk import RSAKey

__all__ = ["PRIVATE_PEM", "PUBLIC_PEM"]

_KEY = RSAKey.generate_key(2048, parameters={"kid": "fixture-1"})
PRIVATE_PEM: str = _KEY.as_pem(private=True).decode("utf-8")
PUBLIC_PEM: str = _KEY.as_pem(private=False).decode("utf-8")
