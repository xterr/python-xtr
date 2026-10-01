"""The security configuration the served OIDC fixture is built from.

A secured ``api`` firewall on ``^/api`` with a bearer access-token authenticator
whose handler is the OIDC one, verifying against a pinned JWKS — no network. The
access-control rule requires authentication on ``^/api``.
"""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.fixtures.oidc_app.keys import AUDIENCE, ISSUER, PUBLIC_JWKS
from xtr_security.bundle import (
    AccessControlConfig,
    AccessTokenConfig,
    FirewallConfig,
    OidcTokenHandlerConfig,
    SecurityConfig,
)

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the served OIDC fixture's security configuration."""
    return SecurityConfig(
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                authenticators=(
                    AccessTokenConfig(
                        token_handler=OidcTokenHandlerConfig(
                            issuers=(ISSUER,),
                            audience=AUDIENCE,
                            keyset=PUBLIC_JWKS,
                            enforce_at_jwt_type=True,
                        ),
                        realm="api",
                    ),
                ),
            ),
        },
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
