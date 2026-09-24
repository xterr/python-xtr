"""Something holding state that must not leak from one unit of work to the next."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["ResettableInterface"]


@runtime_checkable
class ResettableInterface(Protocol):
    """Returns to a clean state between units of work.

    A long-running worker handles many messages or requests in one process.
    Buffers, activated fingers-crossed handlers and generated ids belong to one
    of them; :meth:`reset` ends it, so the next starts clean.
    """

    def reset(self) -> None:
        """Drop per-unit-of-work state, keeping configuration."""
        ...
