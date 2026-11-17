"""Two secured firewalls: one introspecting its tokens (RFC 7662), one reading userinfo."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_security.bundle import (
    AccessTokenConfig,
    FirewallConfig,
    Oauth2TokenHandlerConfig,
    OidcUserInfoTokenHandlerConfig,
    SecurityConfig,
)

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the fixture's security configuration."""
    return SecurityConfig(
        firewalls={
            "introspected": FirewallConfig(
                pattern=r"^/introspected",
                authenticators=(
                    AccessTokenConfig(
                        token_handler=Oauth2TokenHandlerConfig(
                            introspection_base_uri="https://as.example/introspect"
                        )
                    ),
                ),
            ),
            "userinfo": FirewallConfig(
                pattern=r"^/userinfo",
                authenticators=(
                    AccessTokenConfig(
                        token_handler=OidcUserInfoTokenHandlerConfig(
                            userinfo_base_uri="https://as.example/userinfo"
                        )
                    ),
                ),
            ),
        },
    )
