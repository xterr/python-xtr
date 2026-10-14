"""An authorization server storing everything in the default connection's tables.

The same deployment the in-process applications describe, with one line of
configuration changed: ``persistence=OrmPersistenceConfig()``. That is the whole
point of it — every flow has to come out the same against a database, and the
managers that read and write it are singletons that ask the connection registry
for the session of the request being served.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure, env
from xtr_orm.bundle import ConnectionConfig, OrmConfig
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
    OAuth2AuthenticatorConfig,
    OAuth2ServerConfig,
    OrmPersistenceConfig,
    ScopesConfig,
)

__all__ = ["BIND_KEY", "oauth2_server", "orm", "security"]

BIND_KEY: Final = "xtr_security_oauth2_server_test_app"
"""Where this application's table definitions live; its own, so no other test's join them."""

#: The resource owner who approves, and the credential that establishes them.
USER_IDENTIFIER: Final[str] = "grace"
USER_PASSWORD: Final[str] = "the-stored-owners-password"
USER_ROLES: Final[tuple[str, ...]] = ("ROLE_USER",)

#: What the firewall claims: the authorization endpoint and the API, never the
#: token endpoint — authenticating the client there is the server's own job.
PROTECTED: Final[str] = r"^/(authorize|api)"

#: Where the connection's URL is read from, so each test gets a file of its own.
URL_VARIABLE: Final[str] = "OAUTH2_ORM_URL"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run every flow a stored deployment is driven through."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            device_code_verification_uri=f"{ISSUER}/device",
            enable_password_grant=True,
            enable_introspection_endpoint=True,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=OrmPersistenceConfig(),
    )


@configure
def orm() -> OrmConfig:
    """One connection, its definitions under a bind key of this application's own."""
    return OrmConfig(
        connections={
            "default": ConnectionConfig(url=env(URL_VARIABLE), bind_key=BIND_KEY),
        },
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
