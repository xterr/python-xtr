"""A deployment that turned every flow off.

An authorization server running no grant could issue nothing: every request to
its token endpoint would be answered ``unsupported_grant_type``. That is a
deployment mistake rather than a configuration, so the build refuses it.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure

from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["oauth2_server"]

#: A password long enough to be stretched into a key, as the plain mode wants.
ENCRYPTION_KEY: Final[str] = "a-password-long-enough-to-stretch-into-a-key"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Describe a server fully, and then leave it no flow to run."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_client_credentials_grant=False,
            enable_auth_code_grant=False,
            enable_refresh_token_grant=False,
            enable_device_code_grant=False,
            enable_password_grant=False,
            enable_implicit_grant=False,
        ),
        scopes=ScopesConfig(available=("read",), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
