"""A token storage that can drop every token it holds at once."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .token_storage_interface import TokenStorageInterface

__all__ = ["ClearableTokenStorageInterface"]


@runtime_checkable
class ClearableTokenStorageInterface(TokenStorageInterface, Protocol):
    """A token storage that can also drop everything it holds.

    The session strategy is the caller: when a re-authentication rotates
    the session, the tokens minted under the old one must not answer for
    the new — a value stolen before the rotation would otherwise still
    check out after it.
    """

    async def clear(self) -> None:
        """Drop every token this storage holds."""
        ...
