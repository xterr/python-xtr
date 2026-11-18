"""One transition at a time per subject, among the tasks of this process.

A transition reads the subject's marking, asks the guards — who may await —
and writes the marking back. Two tasks applying to one subject object at
once would both read the same marking and both move it, so the move is held
per subject. A listener of the move may apply to the same subject again,
from inside it: the task chain already holding the subject goes straight
through, or it would wait on itself.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

__all__ = ["SubjectLocks"]


@final
class _Hold:
    """A subject a task chain holds; closed once the hold ends.

    A task started while the hold lasted inherits the record through its
    context, and may outlive it: a closed record is not a hold.
    """

    __slots__ = ("closed", "key", "parent")

    def __init__(self, key: tuple[int, int], parent: _Hold | None) -> None:
        self.key = key
        self.parent = parent
        self.closed = False


_HELD: ContextVar[_Hold | None] = ContextVar("xtr_workflow_held_subjects", default=None)


def _is_held(key: tuple[int, int]) -> bool:
    hold = _HELD.get()
    while hold is not None:
        if not hold.closed and hold.key == key:
            return True
        hold = hold.parent
    return False


@final
class _Entry:
    __slots__ = ("lock", "waiters")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.waiters = 0


@final
class SubjectLocks:
    """The locks of one workflow's subjects, by identity, kept only while in use.

    Keyed by ``id()``: stable while a caller holds the subject, defined for an
    unhashable subject, and never asks a subject's ``__eq__``. An entry goes
    when its last waiter leaves, so no lock outlives the loop it ran on.
    """

    __slots__ = ("_entries",)

    def __init__(self) -> None:
        self._entries: dict[int, _Entry] = {}

    @asynccontextmanager
    async def hold(self, subject: object) -> AsyncGenerator[None]:
        """Hold ``subject`` until the block is left; at once when this task chain holds it."""
        key = (id(self), id(subject))
        if _is_held(key):
            yield
            return
        entry = self._entries.get(key[1])
        if entry is None:
            entry = self._entries[key[1]] = _Entry()
        entry.waiters += 1
        try:
            async with entry.lock:
                hold = _Hold(key, _HELD.get())
                token = _HELD.set(hold)
                try:
                    yield
                finally:
                    hold.closed = True
                    _HELD.reset(token)
        finally:
            entry.waiters -= 1
            if entry.waiters == 0:
                del self._entries[key[1]]
