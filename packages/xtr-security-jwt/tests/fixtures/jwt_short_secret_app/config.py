"""An HS256 configuration whose shared secret is far below the algorithm's floor."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_security_jwt.bundle import EncoderConfig, JwtConfig

__all__ = ["jwt"]


@configure
def jwt() -> JwtConfig:
    """Sign with HS256 over a five-byte secret, so the build must refuse it."""
    return JwtConfig(
        secret_key="short",
        issuer="https://jwt.test",
        encoder=EncoderConfig(signature_algorithm="HS256"),
    )
