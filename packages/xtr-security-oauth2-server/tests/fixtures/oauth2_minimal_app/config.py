"""A deployment that turns off everything it is allowed to turn off.

What this fixture is for: an endpoint a deployment does not serve still has a
route — the router is built when the module is imported, before any
configuration is read — so "this server does not do that" has to be said in the
answer. It also proves the device-code verification URI is only required when
the device flow actually runs.
"""

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
    """Run one flow, and serve neither the extras nor the description."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            # Off, so no verification URI is owed: the setting is required only
            # when the flow that shows it to somebody actually runs.
            enable_device_code_grant=False,
            enable_auth_code_grant=False,
            enable_refresh_token_grant=False,
            enable_revocation_endpoint=False,
            enable_introspection_endpoint=False,
            enable_metadata_endpoint=False,
        ),
        scopes=ScopesConfig(available=("read",), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
