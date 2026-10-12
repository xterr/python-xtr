"""What a refresh token answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from .access_token_entity_interface import AccessTokenEntityInterface

__all__ = ["RefreshTokenEntityInterface"]


@runtime_checkable
class RefreshTokenEntityInterface(Protocol):
    """A token that buys a new access token, and names the one it came with.

    It is not a :class:`~xtr_security_oauth2_server_core.entities.token_interface.TokenInterface`:
    a refresh token has no client, no resource owner and no scopes of its own.
    It names an access token, and that token is where all of those are read
    from — which is also why revoking a refresh token can revoke the access
    token it was issued beside.
    """

    def get_identifier(self) -> str:
        """Return the identifier this token is named by."""
        ...

    def set_identifier(self, identifier: str) -> None:
        """Name this token ``identifier``."""
        ...

    def get_expiry_date_time(self) -> datetime:
        """Return the instant this token stops being accepted."""
        ...

    def set_expiry_date_time(self, date_time: datetime) -> None:
        """Stop accepting this token at ``date_time``, which must be aware."""
        ...

    def get_access_token(self) -> AccessTokenEntityInterface:
        """Return the access token this one was issued beside."""
        ...

    def set_access_token(self, access_token: AccessTokenEntityInterface) -> None:
        """Tie this token to ``access_token``."""
        ...
