"""The refresh-token entity a grant issues beside an access token."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
    RefreshTokenEntityInterface,
)
from xtr_security_oauth2_server_core.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server_core.entities.traits.refresh_token_trait import RefreshTokenTrait

__all__ = ["RefreshToken"]


@final
class RefreshToken(EntityTrait, RefreshTokenTrait, RefreshTokenEntityInterface):
    """A refresh token, tied to the access token it was issued beside.

    No client, no resource owner and no scopes of its own: all three are read
    off that access token, which is what lets a refresh reissue exactly what
    was granted the first time.

    The contract comes last of the bases, for the reason
    :class:`~xtr_security_oauth2_server.entity.access_token.AccessToken` gives.
    """
