"""A signing key and nothing else: the issuer is left to its default."""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.bundle import JwtConfig

__all__ = ["jwt"]


@configure
def jwt() -> JwtConfig:
    """Sign with the test key; stamp tokens with the kernel's name."""
    return JwtConfig(secret_key=RSA_PRIVATE_PEM)
