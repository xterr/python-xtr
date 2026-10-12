"""The resource owner a grant writes into a token."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server_core.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server_core.entities.user_entity_interface import UserEntityInterface

__all__ = ["User"]


@final
class User(EntityTrait, UserEntityInterface):
    """A resource owner, reduced to the identifier a token carries.

    What the user converter builds out of whatever the security family
    resolved: the identifier is all the protocol writes into a token and all a
    resource server is handed back, so nothing else travels this far.

    The contract comes last of the bases, for the reason
    :class:`~xtr_security_oauth2_server.entity.access_token.AccessToken` gives.
    """
