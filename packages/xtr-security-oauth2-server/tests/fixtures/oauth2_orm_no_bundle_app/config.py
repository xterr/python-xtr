"""A stored deployment with nothing to read the database through.

The mistake: ``persistence=OrmPersistenceConfig()`` without listing the ORM
bundle, so there is no connection for the tables to belong to and none for the
managers to read.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure

from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    OAuth2ServerConfig,
    OrmPersistenceConfig,
    ScopesConfig,
)

__all__ = ["oauth2_server"]

#: A password long enough to be stretched into a key, as the plain mode wants.
ENCRYPTION_KEY: Final[str] = "a-password-long-enough-to-stretch-into-a-key"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Keep everything in a database nobody opened."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read",)),
        persistence=OrmPersistenceConfig(),
    )
