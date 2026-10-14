"""A deployment that reads access tokens and keeps no record of them.

Keeping no record is what makes this fixture useful: with nothing written down
there is nothing to have been withdrawn, so a token is refused only for what it
says. A reader that stored its tokens would refuse a foreign one twice over —
once for the issuer it claims and once for the row it has no row for — and a
test could not tell which check did the work.
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

#: What the firewall claims.
PROTECTED: Final[str] = r"^/api"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Read tokens claiming this issuer, and write none of them down."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            # The whole point of this fixture: nothing is stored, so nothing
            # can read as withdrawn.
            persist_access_token=False,
            # A server needs at least one flow to be a server at all.
            enable_client_credentials_grant=True,
            enable_auth_code_grant=False,
            enable_refresh_token_grant=False,
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )


@configure
def security() -> SecurityConfig:
    """Put this deployment's own access tokens in front of ``/api``."""
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
