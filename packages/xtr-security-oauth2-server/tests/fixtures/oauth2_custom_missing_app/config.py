"""The same six stores named, with nothing registering any of them.

What a deployment gets wrong: ``persistence.custom`` names the classes, and
forgetting to register them as services leaves every manager interface
pointing at nothing.
"""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.support.custom_stores import (
    ApplicationAccessTokenStore,
    ApplicationAuthorizationCodeStore,
    ApplicationClientStore,
    ApplicationCredentialsRevoker,
    ApplicationDeviceCodeStore,
    ApplicationRefreshTokenStore,
)
from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    CustomPersistenceConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["oauth2_server"]


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Name six stores this application never registers."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read",)),
        persistence=CustomPersistenceConfig(
            access_token_manager=ApplicationAccessTokenStore,
            authorization_code_manager=ApplicationAuthorizationCodeStore,
            client_manager=ApplicationClientStore,
            refresh_token_manager=ApplicationRefreshTokenStore,
            device_code_manager=ApplicationDeviceCodeStore,
            credentials_revoker=ApplicationCredentialsRevoker,
        ),
    )
