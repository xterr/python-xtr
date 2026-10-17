"""A configuration whose user provider also upgrades passwords."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_security_core import InMemoryUser

from tests.fixtures.migration_app.services import MigrationTokenHandler, UpgradingUserProvider
from xtr_security.bundle import (
    AccessControlConfig,
    AccessTokenConfig,
    FirewallConfig,
    NativeHasherConfig,
    Pbkdf2HasherConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
    ServiceUserProviderConfig,
)

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return a configuration reaching the password-migration listener chain."""
    return SecurityConfig(
        providers={"users": ServiceUserProviderConfig(UpgradingUserProvider)},
        password_hashers={
            # Argon2id best, PBKDF2 verifying the stored legacy hash behind it,
            # so a login both verifies and flags the hash for a rehash.
            InMemoryUser: NativeHasherConfig(migrate_from=(Pbkdf2HasherConfig(),)),
        },
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="users",
                authenticators=(
                    AccessTokenConfig(
                        token_handler=ServiceTokenHandlerConfig(MigrationTokenHandler),
                        realm="api",
                    ),
                ),
            ),
        },
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
