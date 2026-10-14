"""A deployment that names the resource its tokens are meant for.

Every other test deployment leaves ``audience`` unset: the token is then
addressed to the client it was issued to, and the reader checks nothing. The
access-token profile wants a token addressed to the resource that reads it, and
a reader that refuses one addressed elsewhere — so this deployment names an
audience, and its firewall reads tokens carrying it.
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

__all__ = ["AUDIENCE", "oauth2_server", "security"]

#: The resource this deployment's tokens are addressed to, and the one its
#: firewall expects to find named in a token it is handed.
AUDIENCE: Final[str] = "https://resource.example.com"

#: The resource owner the password grant resolves to.
USER_IDENTIFIER: Final[str] = "ada"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Issue tokens addressed to one named resource."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            audience=AUDIENCE,
            signature_algorithm=ALGORITHM,
            device_code_verification_uri=f"{ISSUER}/device",
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )


@configure
def security() -> SecurityConfig:
    """Put this deployment's own access tokens in front of ``/api``."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(users={USER_IDENTIFIER: {"roles": []}}),
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
