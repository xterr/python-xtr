"""The one surface every token storage answers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["TokenStorageInterface"]


@runtime_checkable
class TokenStorageInterface(Protocol):
    """Keeps token values by id, wherever the application points them.

    Every member is awaited: one storage must be swappable for another, and
    a remote one is awaited — the session is only the one this library
    ships a storage for.
    """

    async def get_token(self, token_id: str) -> str:
        """Return the value stored under ``token_id``.

        Raises:
            TokenNotFoundError: When no value is stored under the id.
        """
        ...

    async def set_token(self, token_id: str, token: str) -> None:
        """Store ``token`` under ``token_id``, replacing what was there."""
        ...

    async def remove_token(self, token_id: str) -> str | None:
        """Drop the value under ``token_id``.

        Returns:
            The value it held, or ``None`` when it held nothing.
        """
        ...

    async def has_token(self, token_id: str) -> bool:
        """Tell whether a value is stored under ``token_id``."""
        ...
