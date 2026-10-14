"""A deployment that runs the browser redirect flow, proof key required.

The resource owner is authenticated on ``/authorize`` by this deployment's own
access tokens, which is the cheapest arrangement that still exercises the real
thing: the consent event is only reached once somebody is established, and
``Security.get_user()`` is what establishes them. A deployment showing a login
page would put its own firewall there instead; nothing below the controller
knows the difference.

``/token`` is deliberately outside the firewall: authenticating the *client*
there is the authorization server's own job, not a firewall's.
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

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2AuthenticatorConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["oauth2_server", "security"]

#: The resource owner who approves, and the credential that establishes them.
USER_IDENTIFIER: Final[str] = "ada"
USER_PASSWORD: Final[str] = "the-resource-owners-password"
USER_ROLES: Final[tuple[str, ...]] = ("ROLE_USER",)

#: What the firewall claims: the authorization endpoint, where a person is, and
#: the API. Never the token endpoint.
PROTECTED: Final[str] = r"^/(authorize|api)"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run the redirect flow, and the password flow that establishes the owner."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            device_code_verification_uri=f"{ISSUER}/device",
            enable_auth_code_grant=True,
            enable_password_grant=True,
            # The default, named here because the refusals below are what it buys.
            require_code_challenge_for_public_clients=True,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )


@configure
def security() -> SecurityConfig:
    """Establish the resource owner on ``/authorize`` and the caller on ``/api``."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={USER_IDENTIFIER: {"roles": list(USER_ROLES)}},
            ),
        },
        firewalls={
            "api": FirewallConfig(
                pattern=PROTECTED,
                provider="users",
                authenticators=(OAuth2AuthenticatorConfig(),),
            ),
        },
        access_control=(AccessControlConfig(path=PROTECTED, attribute="IS_AUTHENTICATED"),),
    )
