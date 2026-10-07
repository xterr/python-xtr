"""A JWT configuration that would let a firewall read a token from nowhere."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_security_jwt.bundle import (
    AuthorizationHeaderExtractorConfig,
    JwtConfig,
    TokenExtractorsConfig,
)

__all__ = ["jwt"]


@configure
def jwt() -> JwtConfig:
    """Disable the only extractor that was on, so the build must refuse it."""
    return JwtConfig(
        secret_key="a signing key the build never reaches",
        issuer="https://jwt.test",
        token_extractors=TokenExtractorsConfig(
            authorization_header=AuthorizationHeaderExtractorConfig(enabled=False),
        ),
    )
