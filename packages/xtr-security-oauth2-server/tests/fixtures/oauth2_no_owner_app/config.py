"""A deployment that left ``/authorize`` outside its firewall.

The mistake the authorization endpoint has to answer for: a firewall is
configured, but its pattern does not claim the one endpoint a person reaches,
so the request arrives with nobody authenticated and there is no resource owner
to ask for consent.
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

__all__ = ["PROTECTED", "oauth2_server", "security"]

#: What the firewall claims — the API and nothing else. ``/authorize`` is
#: outside it, which is the whole point of this deployment.
PROTECTED: Final[str] = r"^/api"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run the redirect flow, over a store that forgets when the process ends."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )


@configure
def security() -> SecurityConfig:
    """Claim the API, and leave the authorization endpoint unclaimed."""
    return SecurityConfig(
        providers={"users": InMemoryUserProviderConfig(users={"ada": {"roles": ["ROLE_USER"]}})},
        firewalls={
            "api": FirewallConfig(
                pattern=PROTECTED,
                provider="users",
                authenticators=(OAuth2AuthenticatorConfig(),),
            ),
        },
        access_control=(AccessControlConfig(path=PROTECTED, attribute="IS_AUTHENTICATED"),),
    )
