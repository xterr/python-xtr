"""What a stored authorization code answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from xtr_security_oauth2_server.value_object.scope import Scope

    from .client_interface import ClientInterface

__all__ = ["AuthorizationCodeInterface"]


@runtime_checkable
class AuthorizationCodeInterface(Protocol):
    """An authorization code as this server remembers it.

    Stored for exactly one reason: a code may be redeemed once. The token
    endpoint withdraws the code it just exchanged, and a second attempt with
    the same code finds it withdrawn — so the record is what makes single use
    single use.

    It carries what the resource owner consented to as well, because a
    deployment narrowing a token's scopes to that consent reads them back from
    here.
    """

    def get_identifier(self) -> str:
        """Return the identifier this code is stored under."""
        ...

    def get_expiry(self) -> datetime:
        """Return the instant this code stops being accepted."""
        ...

    def get_user_identifier(self) -> str | None:
        """Return the resource owner this code was issued for, or ``None``."""
        ...

    def get_client(self) -> ClientInterface:
        """Return the client this code was issued to."""
        ...

    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes consented to when this code was issued."""
        ...

    def is_revoked(self) -> bool:
        """Tell whether this code has been redeemed or withdrawn."""
        ...

    def revoke(self) -> Self:
        """Withdraw this code, and answer it so a caller can chain."""
        ...

    @override
    def __str__(self) -> str:
        """Return the identifier, so a stored code reads as its name."""
        ...
