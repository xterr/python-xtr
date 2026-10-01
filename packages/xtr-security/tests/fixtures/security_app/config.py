"""The security configuration the served fixture is built from.

A secured ``api`` firewall on ``^/api`` with a bearer access-token authenticator,
an open ``open`` firewall on ``^/open`` (``security=False``), and access-control
rules covering the served tests: a public path, an authenticated path and an
admin path. Password hashers are configured so the user hasher resolves.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_security_core import InMemoryUser

from tests.fixtures.security_app.services import FixtureTokenHandler, FixtureUserProvider
from xtr_security.bundle import (
    AccessControlConfig,
    AccessTokenConfig,
    FirewallConfig,
    NativeHasherConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
    ServiceUserProviderConfig,
)

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the served fixture's security configuration."""
    return SecurityConfig(
        providers={"users": ServiceUserProviderConfig(FixtureUserProvider)},
        password_hashers={InMemoryUser: NativeHasherConfig()},
        role_hierarchy={"ROLE_ADMIN": ["ROLE_USER"]},
        firewalls={
            "open": FirewallConfig(pattern=r"^/open", security=False),
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="users",
                authenticators=(
                    AccessTokenConfig(
                        token_handler=ServiceTokenHandlerConfig(FixtureTokenHandler),
                        realm="api",
                    ),
                ),
            ),
        },
        access_control=(
            AccessControlConfig(path=r"^/api/public", attribute="PUBLIC_ACCESS"),
            AccessControlConfig(path=r"^/api/admin", attribute="ROLE_ADMIN"),
            AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),
        ),
    )
