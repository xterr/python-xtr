"""A stateful firewall whose form login and logout paths are parameter references.

The login paths are parameters written as values; the logout target is a
parameter reading the environment, the way a deployment names its other origin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_dependency_injection import configure, parameters
from xtr_security_core import InMemoryUser

from tests.fixtures.env_paths_app.paths import CHECK_PATH, LOGIN_PATH, LOGOUT_PATH
from xtr_security.bundle import (
    FormLoginConfig,
    InMemoryUserProviderConfig,
    LogoutConfig,
    PlaintextHasherConfig,
    SecurityConfig,
)
from xtr_security.firewall_config import FirewallConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["app_parameters", "security"]


@parameters
def app_parameters() -> Mapping[str, object]:
    """Name every path once."""
    return {
        "app": {
            "login_path": LOGIN_PATH,
            "check_path": CHECK_PATH,
            "logout_path": LOGOUT_PATH,
            "web_app_origin": "%env(WEB_APP_ORIGIN)%",
        }
    }


@configure
def security() -> SecurityConfig:
    """Return the fixture's security configuration, every path a parameter."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={"alice": {"password": "secret", "roles": ["ROLE_USER"], "enabled": True}}
            )
        },
        password_hashers={InMemoryUser: PlaintextHasherConfig()},
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                logout=LogoutConfig(path="%app.logout_path%", target_path="%app.web_app_origin%"),
                authenticators=(
                    FormLoginConfig(
                        login_path="%app.login_path%",
                        check_path="%app.check_path%",
                        post_only=False,
                    ),
                ),
            )
        },
    )
