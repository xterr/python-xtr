"""The bundle wiring this package's authorization server into an application.

An application lists :class:`OAuth2ServerBundle` and writes an
:class:`OAuth2ServerConfig`; everything else here is what that configuration is
made of.
"""

from __future__ import annotations

from .authorization_server_config import AuthorizationServerConfig
from .client_config import ClientConfig
from .encryption_key_pass import EncryptionKeyPass
from .grant_type_pass import GRANT_TAG, GrantTypePass
from .metadata_pass import METADATA_TAG, MetadataPass
from .oauth2_authenticator_config import OAuth2AuthenticatorConfig
from .oauth2_server_bundle import OAUTH2_SERVER_CHANNEL, OAuth2ServerBundle
from .oauth2_server_config import OAuth2ServerConfig
from .persistence_configs import (
    CustomPersistenceConfig,
    InMemoryPersistenceConfig,
    OrmPersistenceConfig,
)
from .resource_server_config import ResourceServerConfig
from .scopes_config import ScopesConfig

__all__ = [
    "GRANT_TAG",
    "METADATA_TAG",
    "OAUTH2_SERVER_CHANNEL",
    "AuthorizationServerConfig",
    "ClientConfig",
    "CustomPersistenceConfig",
    "EncryptionKeyPass",
    "GrantTypePass",
    "InMemoryPersistenceConfig",
    "MetadataPass",
    "OAuth2AuthenticatorConfig",
    "OAuth2ServerBundle",
    "OAuth2ServerConfig",
    "OrmPersistenceConfig",
    "ResourceServerConfig",
    "ScopesConfig",
]
