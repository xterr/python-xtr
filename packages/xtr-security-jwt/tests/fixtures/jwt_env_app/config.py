"""JWT and security configuration reading the signing key and the issuer from env()."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_dependency_injection import configure, env
from xtr_security.bundle import (
    AccessControlConfig,
    FirewallConfig,
    SecurityConfig,
)

from xtr_security_jwt.bundle import JwtAuthenticatorConfig, JwtConfig, JwtUserProviderConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security.bundle import UserProviderConfig

__all__ = ["jwt", "security"]


@configure
def jwt() -> JwtConfig:
    """Sign with the key from env("file:JWT_TEST_KEY_PATH"), stamped with env("JWT_ISSUER")."""
    return JwtConfig(
        secret_key=env("file:JWT_TEST_KEY_PATH"),
        issuer=env("JWT_ISSUER"),
        user_id_claim="username",
    )


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
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
