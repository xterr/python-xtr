"""The stored authorization code: what makes a code redeemable exactly once."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override

from ._short_identifier import short_identifier
from .authorization_code_interface import AuthorizationCodeInterface

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from xtr_security_oauth2_server.value_object.scope import Scope

    from .client_interface import ClientInterface

__all__ = ["AuthorizationCode"]


class AuthorizationCode(AuthorizationCodeInterface):
    """What was consented to, so the code cannot be redeemed twice."""

    def __init__(
        self,
        identifier: str,
        expiry: datetime,
        client: ClientInterface,
        user_identifier: str | None,
        scopes: Sequence[Scope],
    ) -> None:
        """Record a code issued to ``client`` for ``scopes`` until ``expiry``.

        ``scopes`` is copied, so a caller that goes on to change its own list
        does not change what this code says was consented to.
        """
        self._identifier: str = identifier
        self._expiry: datetime = expiry
        self._client: ClientInterface = client
        self._user_identifier: str | None = user_identifier
        self._scopes: tuple[Scope, ...] = tuple(scopes)
        self._revoked: bool = False

    @override
    def get_identifier(self) -> str:
        """Return the identifier this code is stored under."""
        return self._identifier

    @override
    def get_expiry(self) -> datetime:
        """Return the instant this code stops being accepted."""
        return self._expiry

    @override
    def get_user_identifier(self) -> str | None:
        """Return the resource owner this code was issued for, or ``None``."""
        return self._user_identifier

    @override
    def get_client(self) -> ClientInterface:
        """Return the client this code was issued to."""
        return self._client

    @override
    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes consented to when this code was issued."""
        return self._scopes

    @override
    def is_revoked(self) -> bool:
        """Tell whether this code has been redeemed or withdrawn."""
        return self._revoked

    @override
    def revoke(self) -> Self:
        """Withdraw this code, and answer it so a caller can chain."""
        self._revoked = True

        return self

    @override
    def __str__(self) -> str:
        """Return the identifier, so a stored code reads as its name."""
        return self._identifier

    @override
    def __repr__(self) -> str:
        """Name the type and a cut-short identifier, and nothing else."""
        return f"{type(self).__name__}(identifier={short_identifier(self._identifier)!r})"
