"""The application's clock configuration: reporting in UTC."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_clock.bundle import ClockConfig


@configure
def clock() -> ClockConfig:
    """Report every instant in UTC."""
    return ClockConfig(timezone="UTC")
