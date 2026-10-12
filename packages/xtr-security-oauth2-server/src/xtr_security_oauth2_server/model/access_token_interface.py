"""What a stored access token answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from xtr_security_oauth2_server.value_object.scope import Scope

    from .client_interface import ClientInterface

__all__ = ["AccessTokenInterface"]


@runtime_checkable
class AccessTokenInterface(Protocol):
    """An access token as this server remembers it.

    An access token leaves here as a signed document a resource server reads
    on its own, so this record exists for one reason only: to be able to
    withdraw the token before it expires. Everything on it is therefore
    read-only except the revocation, which is the one thing that changes
    after the token was issued.

    A deployment that does not store its access tokens keeps none of these —
    and gives up revoking them in exchange for never looking one up.
    """

    def get_identifier(self) -> str:
        """Return the identifier this token is stored under."""
        ...

    def get_expiry(self) -> datetime:
        """Return the instant this token stops being accepted."""
        ...

    def get_user_identifier(self) -> str | None:
        """Return the resource owner this token acts for, or ``None`` for none."""
        ...

    def get_client(self) -> ClientInterface:
        """Return the client this token was issued to."""
        ...

    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes this token was granted."""
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
