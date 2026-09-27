"""The scheduler: handle scheduled messages on the worker consuming the schedule.

``use_messenger_routing=True`` would send every scheduled message through routing instead;
the shop's schedule does that for one message only, with a ``RedispatchMessage``.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_scheduler.bundle import SchedulerConfig

__all__ = ["scheduler"]


@configure
def scheduler() -> SchedulerConfig:
    """Scheduled messages are handled where the schedule is consumed."""
    return SchedulerConfig(use_messenger_routing=False)
