"""A fully described deployment that also contributes a grant of its own."""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["oauth2_server"]


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Keep the shipped client-credentials flow on, beside the contributed one."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            # The shipped grant stays on, so two grants answer one name.
            enable_client_credentials_grant=True,
            enable_auth_code_grant=False,
            enable_refresh_token_grant=False,
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read",), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
