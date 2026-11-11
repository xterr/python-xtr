"""Where a run stands."""

from __future__ import annotations

from enum import IntEnum, unique

__all__ = ["RunState"]


@unique
class RunState(IntEnum):
    """Where a run stands: running, or one of the three ways it ends."""

    RUNNING = 1
    FINISHED = 2
    CANCELLED = 3
    FAILED = 4

    @property
    def is_terminal(self) -> bool:
        """Whether the run has ended."""
        return self is not RunState.RUNNING
