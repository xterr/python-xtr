"""A refresh token names the access token it was issued beside, and its window."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from xtr_security_oauth2_server.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )

__all__ = ["RefreshTokenTrait"]


class RefreshTokenTrait:
    """Holds the access token a refresh token came with, and when it expires.

    Compose it with the identifier trait and a refresh-token entity is
    complete. There is no client, no resource owner and no set of scopes here:
    all of those are read from the access token this one names, which is what
    lets a refresh exchange reissue exactly what was granted the first time.
    """

    _access_token: AccessTokenEntityInterface
    _expiry_date_time: datetime

    def get_access_token(self) -> AccessTokenEntityInterface:
        """Return the access token this one was issued beside."""
        return self._access_token

    def set_access_token(self, access_token: AccessTokenEntityInterface) -> None:
        """Tie this token to ``access_token``."""
        self._access_token = access_token

    def get_expiry_date_time(self) -> datetime:
        """Return the instant this token stops being accepted."""
        return self._expiry_date_time

    def set_expiry_date_time(self, date_time: datetime) -> None:
        """Stop accepting this token at ``date_time``, which must be aware."""
        self._expiry_date_time = date_time
