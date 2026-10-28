"""The security configuration the remember-me and switch-user fixture is built from.

A stateful ``main`` firewall on ``^/`` with a form login, a remember-me
cookie signed with the fixture's own secret, a switch-user block, login
throttling with generous windows, and one channel rule demanding HTTPS of
the page the channel listener redirects.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_security_core import InMemoryUser

from xtr_security.bundle import (
    AccessControlConfig,
    FormLoginConfig,
    InMemoryUserProviderConfig,
    LoginLinkConfig,
    LoginThrottlingConfig,
    PlaintextHasherConfig,
    RememberMeConfig,
    RemoteUserConfig,
    SecurityConfig,
    SwitchUserConfig,
)
from xtr_security.firewall_config import FirewallConfig

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the fixture's security configuration."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={
                    "alice": {
                        "password": "secret",
                        "roles": ["ROLE_USER", "ROLE_ALLOWED_TO_SWITCH"],
                        "enabled": True,
                    },
                    "bob": {"password": "secret", "roles": ["ROLE_USER"], "enabled": True},
                }
            )
        },
        password_hashers={InMemoryUser: PlaintextHasherConfig()},
        access_control=(
            AccessControlConfig(path=r"^/login$", attribute="PUBLIC_ACCESS"),
            AccessControlConfig(path=r"^/secure$", attribute="PUBLIC_ACCESS", channel="https"),
            AccessControlConfig(path=r"^/", attribute="IS_AUTHENTICATED"),
        ),
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                switch_user=SwitchUserConfig(),
                login_throttling=LoginThrottlingConfig(
                    secret="counting-secret", global_limit=50, local_limit=50
                ),
                authenticators=(
                    FormLoginConfig(login_path="/login", post_only=False, enable_csrf=False),
                    LoginLinkConfig(check_path="/link", path="/login", secret="link-secret"),
                    RemoteUserConfig(),
                    RememberMeConfig(secret="remember-secret"),
                ),
            )
        },
    )
