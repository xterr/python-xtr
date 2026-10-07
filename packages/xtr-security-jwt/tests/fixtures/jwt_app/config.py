"""The fixture application's JWT and security configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_dependency_injection import configure
from xtr_security.bundle import (
    AccessControlConfig,
    FirewallConfig,
    SecurityConfig,
)

from tests.fixtures.jwt_app.keys import PRIVATE_PEM
from xtr_security_jwt.bundle import JwtAuthenticatorConfig, JwtConfig, JwtUserProviderConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security.bundle import UserProviderConfig

__all__ = ["jwt", "security"]


@configure
def jwt() -> JwtConfig:
    """Sign and verify with the fixture key, reading the user from ``username``."""
    return JwtConfig(secret_key=PRIVATE_PEM, issuer="https://jwt.test", user_id_claim="username")


@configure
def security() -> SecurityConfig:
    """Protect ``/api`` with a firewall accepting self-issued tokens."""
    providers = cast("Mapping[str, UserProviderConfig]", {"jwt_users": JwtUserProviderConfig()})
    return SecurityConfig(
        providers=providers,
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="jwt_users",
                authenticators=(JwtAuthenticatorConfig(),),
            ),
        },
        access_control=(
            AccessControlConfig(path=r"^/api/admin", attribute="ROLE_ADMIN"),
            AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),
        ),
    )
