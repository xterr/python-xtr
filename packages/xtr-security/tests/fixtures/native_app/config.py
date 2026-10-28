"""The security configuration the native-params fixture is built from.

A secured ``api`` firewall on ``^/api`` reading the same bearer tokens the
served security fixture knows, with a public slice under ``^/api/open`` — so a
served test can drive routes whose parameters the framework itself resolves
(``Security``, ``HTTPBearer``, ``SecurityScopes``, ``APIKeyHeader``) beside the
firewall the bundle runs over the lifecycle.
"""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.fixtures.native_app.services import NativeTokenHandler
from xtr_security.bundle import (
    AccessControlConfig,
    AccessTokenConfig,
    FirewallConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
)

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the native-params fixture's security configuration."""
    return SecurityConfig(
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                authenticators=(
                    AccessTokenConfig(
                        token_handler=ServiceTokenHandlerConfig(NativeTokenHandler),
                        realm="api",
                    ),
                ),
            ),
        },
        access_control=(
            AccessControlConfig(path=r"^/api/open", attribute="PUBLIC_ACCESS"),
            AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),
        ),
    )
