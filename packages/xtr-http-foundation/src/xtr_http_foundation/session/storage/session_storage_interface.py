"""The port a session's attributes persist through."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["SessionStorageInterface"]


@runtime_checkable
class SessionStorageInterface(Protocol):
    """A persistence port: the attributes in, the attributes out, the entry gone.

    The session owns the attributes, the ID and the rotation; the storage
    persists them, nothing more. Every member is awaited, because one
    storage must be swappable for another and a remote one is awaited.

    The rules:

    - ``read`` answers ``None`` for an ID that holds nothing — an entry
      the backend expired counts as nothing, exactly as one that never was.
    - ``delete`` of an ID that holds nothing is fine, not an error.
    - What a value must be to survive the round trip is the storage's own
      contract, and it is heard at ``write`` — loudly, never a silent loss.
    """

    async def read(self, session_id: str) -> Mapping[str, object] | None:
        """Return the attributes stored under ``session_id``, or ``None`` when it holds nothing.

        Args:
            session_id: The ID whose attributes are asked for.

        Returns:
            The stored attributes, or ``None`` — an expired entry counts
            as nothing, and the session starts fresh.
        """
        ...

    async def write(
        self,
        session_id: str,
        data: Mapping[str, object],
        ttl: float | None,
    ) -> None:
        """Store ``data`` under ``session_id``, the whole of it, to live ``ttl`` seconds.

        A ``ttl`` of ``None`` names no moment to expire at: the entry
        lives as long as the storage is configured to keep it.

        Args:
            session_id: The ID to store the attributes under.
            data: The attributes, all of them at once.
            ttl: How many seconds the entry is to live, or ``None`` for
                the storage's own default.

        Raises:
            InvalidArgumentError: When a value in ``data`` cannot round-trip
                through the storage's format.
            SessionError: When the storage fails to keep the entry.
        """
        ...

    async def delete(self, session_id: str) -> None:
        """Remove the entry under ``session_id``; an ID holding nothing is fine.

        Raises:
            SessionError: When the storage fails to remove the entry.
        """
        ...
