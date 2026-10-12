"""What every issued token answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from .client_entity_interface import ClientEntityInterface
    from .scope_entity_interface import ScopeEntityInterface

__all__ = ["TokenInterface"]


@runtime_checkable
class TokenInterface(Protocol):
    """What a token is: who asked for it, who it is for, how much, until when.

    Access tokens, authorization codes and device codes all answer to this, so
    a grant that issues one and a repository that stores one read the same
    surface whatever kind of token it is. Refresh tokens are the exception —
    one is tied to the access token it was issued beside rather than to a
    client and a set of scopes — and have a contract of their own.

    The accessors are methods, not properties, so an implementation keeps its
    state however it likes — a mapped column, a row of a result set, a plain
    attribute — without this contract naming anything it has to expose.

    An expiry is an aware :class:`~datetime.datetime`: the protocol compares it
    against a clock reading and writes it into a token as a UTC timestamp, and
    both go wrong silently when the offset is left to be guessed.
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

    def get_user_identifier(self) -> str | None:
        """Return the resource owner this token is for, or ``None`` for none.

        A token issued to a client acting for itself names no resource owner.
        """
        ...

    def set_user_identifier(self, identifier: str) -> None:
        """Issue this token on behalf of the resource owner ``identifier``."""
        ...

    def get_client(self) -> ClientEntityInterface:
        """Return the client this token was issued to."""
        ...

    def set_client(self, client: ClientEntityInterface) -> None:
        """Issue this token to ``client``."""
        ...

    def get_scopes(self) -> Sequence[ScopeEntityInterface]:
        """Return the scopes this token carries, in the order they were added."""
        ...

    def add_scope(self, scope: ScopeEntityInterface) -> None:
        """Let this token carry ``scope``."""
        ...
