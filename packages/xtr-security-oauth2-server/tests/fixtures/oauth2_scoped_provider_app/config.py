"""A deployment issuing user-bound tokens, read by a firewall over a provider of the request.

The password flow is on, as the cheapest way to a token naming a resource
owner; the firewall on ``/api`` reads it and loads the owner through
:class:`ScopedUserProvider`, a service of the request.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure
from xtr_security.bundle import (
    AccessControlConfig,
    FirewallConfig,
    SecurityConfig,
    ServiceUserProviderConfig,
)

from tests.fixtures.oauth2_scoped_provider_app.services import ScopedUserProvider
from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2AuthenticatorConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["USER_IDENTIFIER", "USER_PASSWORD", "oauth2_server", "security"]

#: The resource owner this deployment knows, and the credential it accepts.
USER_IDENTIFIER: Final[str] = "ada"
USER_PASSWORD: Final[str] = "the-resource-owners-password"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run the password flow, so a token names a resource owner."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            device_code_verification_uri=f"{ISSUER}/device",
            enable_password_grant=True,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )


@configure
def security() -> SecurityConfig:
    """Put this deployment's own access tokens in front of ``/api``, over the scoped provider."""
    return SecurityConfig(
        providers={"users": ServiceUserProviderConfig(ScopedUserProvider)},
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="users",
                authenticators=(OAuth2AuthenticatorConfig(),),
            ),
        },
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
