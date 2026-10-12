"""The scope entity a grant hands around."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface
from xtr_security_oauth2_server.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server.entities.traits.scope_trait import ScopeTrait

__all__ = ["Scope"]


@final
class Scope(EntityTrait, ScopeTrait, ScopeEntityInterface):
    """A scope, named by its identifier and reading as it.

    The whole of it is the identifier, and reading it gives that identifier —
    which is what lets a set of scopes be written into an encrypted payload or
    a token response as a list of names.

    The contract comes last of the bases, for the reason
    :class:`~xtr_security_oauth2_server.entity.access_token.AccessToken` gives.
    """
