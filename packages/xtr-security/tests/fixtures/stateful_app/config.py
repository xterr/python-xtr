"""The security configuration the stateful fixture is built from.

A stateful ``main`` firewall on ``^/`` with an OIDC login against a stand-in
provider — no network: the discovery fetches lazily, so the wiring builds —
a logout with every listener turned on, a back-channel logout recording into
the fixture's cache pool, and the provider's own session ended on logout.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_security_http import ClearedCookie

from xtr_security.bundle import (
    InMemoryUserProviderConfig,
    LogoutConfig,
    OidcBackChannelLogoutConfig,
    OidcEndSessionConfig,
    OidcLoginConfig,
    SecurityConfig,
)
from xtr_security.firewall_config import FirewallConfig

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the stateful fixture's security configuration."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={"alice": {"password": "hashed", "roles": ["ROLE_USER"], "enabled": True}}
            )
        },
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                session_strategy="migrate",
                logout=LogoutConfig(
                    path="/logout",
                    target_path="/",
                    clear_site_data=("cache",),
                    cookie_clearing={"rememberme": ClearedCookie(path="/")},
                ),
                authenticators=(
                    OidcLoginConfig(
                        issuer="https://issuer.example",
                        client_id="shop",
                        client_secret="secret",
                        signature_verifier_algorithms=("RS256",),
                        backchannel_logout=OidcBackChannelLogoutConfig(route="/logout/backchannel"),
                        end_session=OidcEndSessionConfig(post_logout_redirect_path="/bye"),
                    ),
                ),
            )
        },
    )
