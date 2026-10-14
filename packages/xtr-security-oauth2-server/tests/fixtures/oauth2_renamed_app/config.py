"""A fully configured authorization server, keeping everything in memory."""

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

__all__ = ["oauth2_server"]

#: The key minted once for the whole suite, as the PEM a deployment would mount.
PRIVATE_KEY: Final[str] = SIGNING_KEY_PEM

#: Where a person is told to go to type a device's user code.
VERIFICATION_URI: Final[str] = f"{ISSUER}/device"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run every shipped flow, over the scopes the suite asserts on."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=PRIVATE_KEY,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            device_code_verification_uri=VERIFICATION_URI,
            enable_password_grant=True,
            enable_implicit_grant=True,
            enable_introspection_endpoint=True,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
