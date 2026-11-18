"""A session storage that keeps its entries in the process's own memory."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from ._json_values import decoded, encoded
from .session_storage_interface import SessionStorageInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["MemorySessionStorage"]


@final
class MemorySessionStorage(SessionStorageInterface):
    """Keeps the sessions of one process, for as long as the process lives.

    The zero-configuration storage and the test default: no entry survives
    a restart and no two servers share one, so an application that needs
    either points the session at a storage of its own. The ``ttl`` a write
    names is not counted — counting it would need a clock, and the entries
    live exactly as long as the process anyway.

    Entries are kept as the JSON the cache-pool storage writes, so a value
    that storage refuses is refused here too, and what a reader gets is a
    copy of its own: changing it reaches no other request.
    """

    __slots__ = ("_sessions",)

    def __init__(self) -> None:
        """Keep no session yet."""
        self._sessions: dict[str, str] = {}

    @override
    async def read(self, session_id: str) -> Mapping[str, object] | None:
        """Return the attributes stored under ``session_id``, or ``None`` when it holds nothing."""
        text = self._sessions.get(session_id)
        return None if text is None else decoded(text)

    @override
    async def write(
        self,
        session_id: str,
        data: Mapping[str, object],
        ttl: float | None,
        *,
        must_exist: bool = False,
    ) -> bool:
        """Store ``data`` under ``session_id``, copied in, whatever the ``ttl`` names.

        Returns:
            ``False`` when ``must_exist`` is set and the entry is gone, so
            nothing was written; ``True`` otherwise.

        Raises:
            InvalidArgumentError: When a value in ``data`` cannot round-trip
                through JSON.
        """
        del ttl
        text = encoded(data)
        if must_exist and session_id not in self._sessions:
            return False
        self._sessions[session_id] = text
        return True

    @override
    async def delete(self, session_id: str) -> None:
        """Remove the entry under ``session_id``; an ID holding nothing is fine."""
        _ = self._sessions.pop(session_id, None)
