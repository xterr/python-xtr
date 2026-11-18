"""One stretch of time an event ran for."""

from __future__ import annotations

from typing import final, override

__all__ = ["StopwatchPeriod"]


@final
class StopwatchPeriod:
    """One start and the stop that closed it.

    Both ends are milliseconds from the origin of the event the period belongs
    to, so periods of one event — and of every event of one section — line up
    on the same axis.
    """

    __slots__ = ("_end", "_start")

    def __init__(self, start: float, end: float) -> None:
        """Record a period from ``start`` to ``end``, both in milliseconds from the origin."""
        self._start = start
        self._end = end

    @property
    def start(self) -> float:
        """When the period began, in milliseconds from the origin."""
        return self._start

    @property
    def end(self) -> float:
        """When the period ended, in milliseconds from the origin."""
        return self._end

    @property
    def duration(self) -> float:
        """How long the period lasted, in milliseconds."""
        return self._end - self._start

    def to_dict(self) -> dict[str, float]:
        """Return the period as plain data: ``start``, ``end`` and ``duration``."""
        return {"start": self._start, "end": self._end, "duration": self.duration}

    @override
    def __repr__(self) -> str:
        """Return the period's span, which is all there is to see."""
        return f"{type(self).__name__}(start={self._start:.3f}, end={self._end:.3f})"
