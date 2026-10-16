"""A session storage that keeps its entries in the process's own memory."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

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
    """

    __slots__ = ("_sessions",)

    def __init__(self) -> None:
        """Keep no session yet."""
        self._sessions: dict[str, dict[str, object]] = {}

    @override
    async def read(self, session_id: str) -> Mapping[str, object] | None:
        """Return the attributes stored under ``session_id``, or ``None`` when it holds nothing."""
        return self._sessions.get(session_id)

    @override
    async def write(self, session_id: str, data: Mapping[str, object], ttl: float | None) -> None:
        """Store ``data`` under ``session_id``, copied in, whatever the ``ttl`` names.

        The mapping is copied, so the caller's own attributes are not held:
        a session that keeps writing after this call must not reach the
        stored entry without saving again.
        """
        del ttl
        self._sessions[session_id] = dict(data)

    @override
    async def delete(self, session_id: str) -> None:
        """Remove the entry under ``session_id``; an ID holding nothing is fine."""
        _ = self._sessions.pop(session_id, None)
