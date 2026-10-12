"""A deployment running both token bundles side by side, each with its own key.

The documented arrangement: one firewall signs the end user in with a
self-issued token, and this server signs the access tokens an API reads. Each
bundle owns its own signing key, which is why this package never registers or
aliases the unqualified key loader and JWS provider — those belong to the
self-issued-token package, and a deployment running both must not have one
bundle quietly signing with the other's key.

The two are deliberately different kinds of key: a shared secret for the
self-issued tokens, a key pair for the access tokens. Nothing could confuse
them for each other.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure
from xtr_security_jwt.bundle import EncoderConfig, JwtConfig

from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["jwt", "oauth2_server"]

#: A password long enough to be stretched into a key, as the plain mode wants.
ENCRYPTION_KEY: Final[str] = "a-password-long-enough-to-stretch-into-a-key"

#: What the self-issued tokens are signed with: a shared secret, long enough
#: for the algorithm's floor and nothing like this server's key pair.
JWT_SECRET: Final[str] = "a-shared-secret-for-the-login-tokens-only"

#: Who the self-issued tokens claim, which is not who the access tokens claim.
JWT_ISSUER: Final[str] = "https://login.example.com"


@configure
def jwt() -> JwtConfig:
    """Sign the end user in with a shared secret of the login side's own."""
    return JwtConfig(
        secret_key=JWT_SECRET,
        issuer=JWT_ISSUER,
        encoder=EncoderConfig(signature_algorithm="HS256"),
    )


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Sign the access tokens with this server's own key pair."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_client_credentials_grant=True,
            enable_auth_code_grant=False,
            enable_refresh_token_grant=False,
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read",), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
