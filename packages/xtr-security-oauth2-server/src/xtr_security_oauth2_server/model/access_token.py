"""The stored access token: issued once, read only to be withdrawn."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override

from ._short_identifier import short_identifier
from .access_token_interface import AccessTokenInterface

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from xtr_security_oauth2_server.value_object.scope import Scope

    from .client_interface import ClientInterface

__all__ = ["AccessToken"]


class AccessToken(AccessTokenInterface):
    """What was issued, so that it can be withdrawn before it expires."""

    def __init__(
        self,
        identifier: str,
        expiry: datetime,
        client: ClientInterface,
        user_identifier: str | None,
        scopes: Sequence[Scope],
    ) -> None:
        """Record a token issued to ``client`` for ``scopes`` until ``expiry``.

        ``user_identifier`` is ``None`` when the client acts for itself.
        ``scopes`` is copied, so a caller that goes on to change its own list
        does not change what this token says it was granted.
        """
        self._identifier: str = identifier
        self._expiry: datetime = expiry
        self._client: ClientInterface = client
        self._user_identifier: str | None = user_identifier
        self._scopes: tuple[Scope, ...] = tuple(scopes)
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
    def get_user_identifier(self) -> str | None:
        """Return the resource owner this token acts for, or ``None`` for none."""
        return self._user_identifier

    @override
    def get_client(self) -> ClientInterface:
        """Return the client this token was issued to."""
        return self._client

    @override
    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes this token was granted."""
        return self._scopes

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
