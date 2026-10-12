"""A deployment that checks a resource owner's own credentials and rotates refresh tokens.

The flow that hands a person's password to a client is off by default and on
here, because it is the cheapest way to get a *user-bound* token — one naming a
resource owner rather than the client itself — and the only shipped flow that
issues a refresh token without a browser being involved.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure
from xtr_security.bundle import (
    AccessControlConfig,
    FirewallConfig,
    InMemoryUserProviderConfig,
    SecurityConfig,
)

from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2AuthenticatorConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["oauth2_server", "security"]

#: A password long enough to be stretched into a key, as the plain mode wants.
ENCRYPTION_KEY: Final[str] = "a-password-long-enough-to-stretch-into-a-key"

#: The resource owner this deployment knows, and the credential it accepts.
USER_IDENTIFIER: Final[str] = "ada"
USER_PASSWORD: Final[str] = "the-resource-owners-password"
USER_ROLES: Final[tuple[str, ...]] = ("ROLE_USER",)


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run the password and refresh-token flows, withdrawing a redeemed refresh token."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            device_code_verification_uri=f"{ISSUER}/device",
            enable_password_grant=True,
            # The default, named here because the reuse refusal is what it buys.
            revoke_refresh_tokens=True,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )


@configure
def security() -> SecurityConfig:
    """Put this deployment's own access tokens in front of ``/api``."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={USER_IDENTIFIER: {"roles": list(USER_ROLES)}},
            ),
        },
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="users",
                authenticators=(OAuth2AuthenticatorConfig(),),
            ),
        },
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
