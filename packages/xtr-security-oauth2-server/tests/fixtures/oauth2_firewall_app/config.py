"""An authorization server whose own API is read by its own access tokens.

The deployment the resource-server side is documented for: one process issues
the tokens and reads them, so the firewall on ``/api`` accepts exactly what the
token endpoint hands out.
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

#: The resource owner the password grant resolves to, and the roles they hold
#: beside whatever a token's scopes grant.
USER_IDENTIFIER: Final[str] = "ada"
USER_ROLES: Final[tuple[str, ...]] = ("ROLE_USER",)


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Issue tokens for the two scopes the API's routes ask for."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            device_code_verification_uri=f"{ISSUER}/device",
            enable_introspection_endpoint=True,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )


@configure
def security() -> SecurityConfig:
    """Put this deployment's own access tokens in front of ``/api``.

    The access-control rule is what makes a token *required*: a firewall alone
    only reads one when it is offered, so without the rule an unauthenticated
    request would reach the endpoint as nobody rather than be challenged.
    """
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
