"""What the authorization server's tokens, clients, scopes and users answer to.

Every name here is a contract, not a class to instantiate: the library issues,
stores and reads tokens through them, and an application brings whatever it
keeps its data in. The traits in
:mod:`xtr_security_oauth2_server_core.entities.traits` are the shortest way to meet
them — compose the ones for the entity being written and the accessors come
with them.

:class:`AccessTokenSigner` is the exception: a value an access token is handed
so it can sign itself, built once per deployment and passed down unchanged.
"""

from __future__ import annotations

from .access_token_entity_interface import AccessTokenEntityInterface
from .access_token_signer import AccessTokenSigner
from .auth_code_entity_interface import AuthCodeEntityInterface
from .client_entity_interface import ClientEntityInterface
from .device_code_entity_interface import DeviceCodeEntityInterface
from .refresh_token_entity_interface import RefreshTokenEntityInterface
from .scope_entity_interface import ScopeEntityInterface
from .token_interface import TokenInterface
from .user_entity_interface import UserEntityInterface

__all__ = [
    "AccessTokenEntityInterface",
    "AccessTokenSigner",
    "AuthCodeEntityInterface",
    "ClientEntityInterface",
    "DeviceCodeEntityInterface",
    "RefreshTokenEntityInterface",
    "ScopeEntityInterface",
    "TokenInterface",
    "UserEntityInterface",
]
