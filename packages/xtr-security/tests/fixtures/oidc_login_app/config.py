"""The security configuration the served OIDC login fixture is built from.

A stateful ``main`` firewall on ``^/`` signs its users in with an OIDC login,
its callback on the login's default path. The account pages need a signed-in
user, so an anonymous visit to one is sent to the provider. The provider is
the test's to stand up, behind the HTTP client the bundle registers for the
firewall. The application signs in with nothing else, so a callback that fails
is sent to a page of its own rather than to a login page it does not have.

The client is confidential and its ID token comes straight from the token
endpoint, so the login reads the token's claims without verifying its
signature — the case OpenID Connect Core 1.0, Section 3.1.3.7, item 6 allows.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure

from xtr_security.bundle import (
    AccessControlConfig,
    InMemoryUserProviderConfig,
    OidcLoginConfig,
    SecurityConfig,
)
from xtr_security.firewall_config import FirewallConfig

__all__ = ["CLIENT_ID", "FAILURE_PATH", "ISSUER", "security"]

#: The provider the login signs in with.
ISSUER: Final = "https://issuer.example"

#: The client the provider knows the fixture by.
CLIENT_ID: Final = "shop"

#: Where a callback that fails is sent.
FAILURE_PATH: Final = "/sign-in-failed"


@configure
def security() -> SecurityConfig:
    """Return the served OIDC login fixture's security configuration."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(users={"alice": {"roles": ["ROLE_USER"]}}),
        },
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                authenticators=(
                    OidcLoginConfig(
                        issuer=ISSUER,
                        client_id=CLIENT_ID,
                        client_secret="secret",
                        user_data_source="id_token",
                        failure_path=FAILURE_PATH,
                    ),
                ),
            ),
        },
        access_control=(AccessControlConfig(path=r"^/account", attribute="IS_AUTHENTICATED"),),
    )
