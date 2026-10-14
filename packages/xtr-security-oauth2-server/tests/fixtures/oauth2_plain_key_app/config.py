"""A deployment whose encryption key is a password, which the bundle stretches into one.

Every other application in this suite hands over the key itself, because
stretching a password is slow on purpose and paid each time a container builds
the servers. This one is where the ``plain`` kind is still driven end to end:
it runs the password and refresh-token flows, so a refresh token is sealed with
the stretched key and opened with it again.
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

__all__ = ["ENCRYPTION_PASSWORD", "oauth2_server"]

#: A password long enough to be stretched into a key, as the plain kind wants.
ENCRYPTION_PASSWORD: Final[str] = "a-password-long-enough-to-stretch-into-a-key"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run the password and refresh-token flows, sealing with a stretched password."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_PASSWORD,
            encryption_key_type="plain",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_device_code_grant=False,
            enable_password_grant=True,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
