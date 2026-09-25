"""Freeze the clock for a test, and restore it after.

Importing this module costs nothing beyond the library itself — it needs no
test framework. The pytest fixture built on it lives in
:mod:`xtr_clock.pytest_plugin`.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from .clock import Clock
from .mock_clock import MockClock

if TYPE_CHECKING:
    from collections.abc import Generator
    from datetime import datetime, tzinfo

__all__ = ["mock_time"]


@contextmanager
def mock_time(
    when: datetime | str | None = None,
    timezone: str | tzinfo | None = None,
) -> Generator[MockClock, None, None]:
    """Install a frozen clock for the duration of a ``with`` block.

    Everything that asks :meth:`~xtr_clock.clock.Clock.get` — including
    :func:`~xtr_clock.now.now` and :meth:`DatePoint.now
    <xtr_clock.date_point.DatePoint.now>` — sees the frozen clock inside the
    block, and the clock that was in force before comes back on the way out,
    including when the block raises.

    ```python
    with mock_time("2024-04-09 12:00:00") as clock:
        assert now().isoformat() == "2024-04-09T12:00:00+00:00"
        clock.sleep(3600)
        assert now().hour == 13
    ```

    Nesting composes: a relative ``when`` is read against the clock already
    in force, so ``mock_time("+1 day")`` inside the block above freezes at
    the 10th.

    In async code prefer calling this inside the coroutine rather than from
    a fixture that finishes before the coroutine starts, so the block and
    the code it covers share one context.

    Args:
        when: Where to freeze. See :class:`~xtr_clock.mock_clock.MockClock`.
        timezone: The zone to report in. Defaults to UTC.

    Yields:
        The frozen clock, so a test can :meth:`~MockClock.sleep` or
        :meth:`~MockClock.modify` it forward.
    """
    clock = MockClock(when, timezone)
    with Clock.using(clock):
        yield clock
