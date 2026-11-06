"""A deployment whose issuer is an environment variable, as each deployment sets its own.

The variable is read when the first service needing the issuer is built, the
same moment the signing key a recipe-written configuration reads is.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure, env

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["ISSUER_VARIABLE", "oauth2_server"]

ISSUER_VARIABLE: Final[str] = "OAUTH2_SERVER_ISSUER"
"""The variable the issuer is read from."""


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Issue tokens under the origin the variable names."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            issuer=env(ISSUER_VARIABLE),
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read",), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
