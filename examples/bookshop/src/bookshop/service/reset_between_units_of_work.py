"""A shutdown hook resetting every built resettable service."""

from __future__ import annotations

from xtr_dependency_injection import Injected, ServicesResetter, on_shutdown

__all__ = ["reset_between_units_of_work"]


@on_shutdown(priority=10)
async def reset_between_units_of_work(resetter: Injected[ServicesResetter]) -> None:
    """Reset every built resettable service — what a worker does after each message."""
    await resetter.reset()
