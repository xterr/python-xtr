"""Turning a stored path into an address that stops working."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from xtr_storage.config import Config

__all__ = ["TemporaryUrlGeneratorInterface"]


@runtime_checkable
class TemporaryUrlGeneratorInterface(Protocol):
    """Hands out an address that carries its own permission, and loses it in time.

    How a private file reaches a browser without the application streaming the
    bytes: the address is signed, whoever holds it may fetch that one file, and
    after the moment it was signed for it leads nowhere.

    Usually satisfied by an adapter whose backend can sign — a storage looks
    for that at runtime — but a generator of one's own may be put in front
    instead.
    """

    async def temporary_url(self, path: str, expires_at: datetime, config: Config) -> str:
        """Return an address for the file at ``path``, good until ``expires_at``.

        Args:
            path: The file to address, already normalized.
            expires_at: When the address stops working. A storage has already
                refused a moment carrying no timezone, so this names one
                instant everywhere.
            config: The options in force.

        Returns:
            An absolute URL.

        Raises:
            UnableToGenerateTemporaryUrlError: When the address could not be
                built or signed.
        """
        ...
