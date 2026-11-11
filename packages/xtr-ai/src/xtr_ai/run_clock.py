"""The clock a run's ``timeout`` is measured against."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic_ai.capabilities import AbstractCapability
from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from xtr_clock import ClockInterface

__all__ = ["RunClock"]


# Not final: a final subclass must initialise the keyword-only marker pydantic-ai's capability
# base declares, which only that base's own dataclass machinery sets.
@dataclass
class RunClock(AbstractCapability[Any]):
    """Measures a run's deadline against ``clock`` instead of the system clock.

    pydantic-ai reads a run's start time, and the time left before its
    ``timeout``, from this clock — also for a run started inside another, which
    inherits the outer deadline. Message timestamps are not affected: pydantic-ai
    stamps those from the system clock.
    """

    clock: ClockInterface

    @override
    def get_run_clock(self) -> Callable[[], datetime]:
        return self.clock.now

    @classmethod
    @override
    def get_serialization_name(cls) -> str | None:
        # Built in code around an injected clock; it has no declarative form.
        return None
