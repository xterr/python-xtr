"""A deployment that runs everything this server ships, with every endpoint on.

The conformance suite needs one deployment where a flow that issues a refresh
token and an endpoint that reads one are both available: the standards say
things about refresh tokens at the revocation and introspection endpoints, and
no other test deployment has both the flow and the endpoints. Nothing here is
unusual — it is the fully configured server, with the two endpoints a
deployment opts into turned on.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["USER_IDENTIFIER", "USER_PASSWORD", "USER_ROLES", "oauth2_server"]

#: The resource owner this deployment knows, and the credential it accepts.
USER_IDENTIFIER: Final[str] = "ada"
USER_PASSWORD: Final[str] = "the-resource-owners-password"
USER_ROLES: Final[tuple[str, ...]] = ("ROLE_USER",)


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run every shipped flow and open every endpoint."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            device_code_verification_uri=f"{ISSUER}/device",
            enable_password_grant=True,
            enable_implicit_grant=True,
            enable_introspection_endpoint=True,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
