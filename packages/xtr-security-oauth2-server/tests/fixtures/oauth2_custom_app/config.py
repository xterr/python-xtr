"""An authorization server reading everything through the application's own stores."""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.fixtures.oauth2_custom_app.stores import (
    AccessTokenStore,
    AuthorizationCodeStore,
    ClientStore,
    CredentialsRevoker,
    DeviceCodeStore,
    RefreshTokenStore,
)
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
    """Name the six stores this application answers for itself."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key="a-password-long-enough-to-stretch-into-a-key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=CustomPersistenceConfig(
            access_token_manager=AccessTokenStore,
            authorization_code_manager=AuthorizationCodeStore,
            client_manager=ClientStore,
            refresh_token_manager=RefreshTokenStore,
            device_code_manager=DeviceCodeStore,
            credentials_revoker=CredentialsRevoker,
        ),
    )
