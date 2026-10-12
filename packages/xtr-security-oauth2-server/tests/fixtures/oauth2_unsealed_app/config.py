"""A deployment with a signing key, a name, a vocabulary and a store — and no seal.

The one setting left out is ``authorization_server.encryption_key``, which is
what an authorization code and a refresh token are sealed with. Everything
else is described, so what a server asked for reports is that one setting and
not the first of four.
"""

from __future__ import annotations

from xtr_dependency_injection import configure

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
    """Describe a working server, save for the key its own payloads are sealed with."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read",), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
