"""What a stored refresh token answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from typing_extensions import override

if TYPE_CHECKING:
    from datetime import datetime

    from .access_token_interface import AccessTokenInterface

__all__ = ["RefreshTokenInterface"]


@runtime_checkable
class RefreshTokenInterface(Protocol):
    """A refresh token as this server remembers it.

    It names the access token it was issued beside and nothing else: the
    client, the resource owner and the scopes are all read from that token,
    which is what lets a refresh reissue exactly what was granted the first
    time, and what lets revoking a refresh token take its access token with
    it.

    The access token may be absent, because a deployment that stores no access
    token still stores its refresh tokens — it simply has nothing to point
    them at.
    """

    def get_identifier(self) -> str:
        """Return the identifier this token is stored under."""
        ...

    def get_expiry(self) -> datetime:
        """Return the instant this token stops being accepted."""
        ...

    def get_access_token(self) -> AccessTokenInterface | None:
        """Return the access token this one came with, or ``None`` when unstored."""
        ...

    def is_revoked(self) -> bool:
        """Tell whether this token has been withdrawn."""
        ...

    def revoke(self) -> Self:
        """Withdraw this token, and answer it so a caller can chain."""
        ...

    @override
    def __str__(self) -> str:
        """Return the identifier, so a stored token reads as its name."""
        ...
