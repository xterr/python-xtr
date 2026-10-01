"""What holds the token for the current unit of work."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["TokenStorageInterface"]


@runtime_checkable
class TokenStorageInterface(Protocol):
    """The one place the authenticated token lives for a unit of work.

    Authentication writes a token here; everything downstream — an access
    decision, a facade reading the current user, a listener turning an error
    into a response — reads it from here. Reading and writing are synchronous:
    the token is already in hand by the time it is stored.
    """

    def get_token(self) -> TokenInterface | None:
        """Return the current token, or ``None`` when none was set."""
        ...

    def set_token(self, token: TokenInterface | None) -> None:
        """Store ``token`` as the current one, or clear it with ``None``."""
        ...
