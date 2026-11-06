"""A deployment whose issuer is a parameter, the parameter reading the environment.

The reference is resolved before the bundle loads, into the placeholder the
parameter holds; the variable itself is read where the issuer is used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_dependency_injection import configure, parameters

from tests.fixtures.oauth2_env_issuer_app.config import ISSUER_VARIABLE
from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["app_parameters", "oauth2_server"]


@parameters
def app_parameters() -> Mapping[str, object]:
    """Name the issuer once, for every configuration that needs it."""
    return {"app": {"issuer": f"%env({ISSUER_VARIABLE})%"}}


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Issue tokens under the origin the parameter names."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            issuer="%app.issuer%",
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read",), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
