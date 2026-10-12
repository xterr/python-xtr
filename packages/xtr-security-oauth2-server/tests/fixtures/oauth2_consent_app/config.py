"""A deployment whose consent is asked for rather than assumed.

The same shape as the redirect-flow application, with one difference: its
listener answers the browser itself on the first pass — the consent page — and
approves on the second, when the form has posted the original query back. That
is what makes consent stateless: nothing is remembered between the two.
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

__all__ = ["USER_IDENTIFIER", "USER_PASSWORD", "USER_ROLES", "oauth2_server", "security"]

#: A password long enough to be stretched into a key, as the plain mode wants.
ENCRYPTION_KEY: Final[str] = "a-password-long-enough-to-stretch-into-a-key"

#: The resource owner who is asked, and the credential that establishes them.
USER_IDENTIFIER: Final[str] = "hedy"
USER_PASSWORD: Final[str] = "the-asked-owners-password"
USER_ROLES: Final[tuple[str, ...]] = ("ROLE_USER",)

#: What the firewall claims: the authorization endpoint and nothing else here.
PROTECTED: Final[str] = r"^/authorize"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run the redirect flow, with the unhashed proof key available to a client."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_password_grant=True,
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )


@configure
def security() -> SecurityConfig:
    """Establish the resource owner on the authorization endpoint."""
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
