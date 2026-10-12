"""The shortest way to satisfy the entity contracts: compose these.

Each trait carries the state and the accessors of one part of an entity, so an
application writes ``class AccessToken(EntityTrait, TokenEntityTrait,
AccessTokenTrait)`` and has a complete access token — the identifier, what the
token is for, and the signing — without writing an accessor.

None of them declares slots, and none of them has a constructor. Two mixins
that each claim slots cannot be combined, and an entity composes three or four
of them; a constructor would have to be called once per trait. State that needs
a default therefore carries it as a class attribute, and state that does not
appears when it is first set.
"""

from __future__ import annotations

from .access_token_trait import AccessTokenTrait
from .auth_code_trait import AuthCodeTrait
from .client_trait import ClientTrait
from .device_code_trait import DeviceCodeTrait
from .entity_trait import EntityTrait
from .refresh_token_trait import RefreshTokenTrait
from .scope_trait import ScopeTrait
from .token_entity_trait import TokenEntityTrait

__all__ = [
    "AccessTokenTrait",
    "AuthCodeTrait",
    "ClientTrait",
    "DeviceCodeTrait",
    "EntityTrait",
    "RefreshTokenTrait",
    "ScopeTrait",
    "TokenEntityTrait",
]
