"""The stored refresh token, pointing at the access token it came with."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override

from ._short_identifier import short_identifier
from .refresh_token_interface import RefreshTokenInterface

if TYPE_CHECKING:
    from datetime import datetime

    from .access_token_interface import AccessTokenInterface

__all__ = ["RefreshToken"]


class RefreshToken(RefreshTokenInterface):
    """A refresh token, and the access token it was issued beside."""

    _access_token: AccessTokenInterface | None = None
    """What a refresh token names when nothing was stored about it.

    Declared on the class, not only set in the constructor, because a stored
    deployment that keeps no access tokens maps no column for this and reads a
    token back without running the constructor. The answer is then the truth:
    the access token this one was issued beside was never written down.
    """

    def __init__(
        self,
        identifier: str,
        expiry: datetime,
        access_token: AccessTokenInterface | None = None,
    ) -> None:
        """Record a refresh token valid until ``expiry``, beside ``access_token``."""
        self._identifier: str = identifier
        self._expiry: datetime = expiry
        self._access_token = access_token
        self._revoked: bool = False

    @override
    def get_identifier(self) -> str:
        """Return the identifier this token is stored under."""
        return self._identifier

    @override
    def get_expiry(self) -> datetime:
        """Return the instant this token stops being accepted."""
        return self._expiry

    @override
    def get_access_token(self) -> AccessTokenInterface | None:
        """Return the access token this one came with, or ``None`` when unstored."""
        return self._access_token

    @override
    def is_revoked(self) -> bool:
        """Tell whether this token has been withdrawn."""
        return self._revoked

    @override
    def revoke(self) -> Self:
        """Withdraw this token, and answer it so a caller can chain."""
        self._revoked = True

        return self

    @override
    def __str__(self) -> str:
        """Return the identifier, so a stored token reads as its name."""
        return self._identifier

    @override
    def __repr__(self) -> str:
        """Name the type and a cut-short identifier, and nothing else."""
        return f"{type(self).__name__}(identifier={short_identifier(self._identifier)!r})"
