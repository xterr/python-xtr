"""The growth check passes a linear cost and fails a quadratic one, at a small size first.

Each case charges its cost to a fake CPU clock rather than spending it, so the verdict is the
check's arithmetic alone: a real clock makes the quadratic case pass on a runner fast enough
that the cost reaches the floor only at the last step, with no later step left to confirm it.
The fake stands in for the whole ``time`` module the check reads, and carries nothing but
``thread_time``, so a check reading any other clock fails here too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from tests.support import growth
from tests.support.growth import assert_linear_growth

if TYPE_CHECKING:
    from collections.abc import Callable

#: Large enough that the last steps of a linear cost take longer than the check's floor.
_TIMED_SIZE = 6_000_000
#: Large enough that the last steps of a quadratic cost take longer than the check's floor.
_QUADRATIC_SIZE = 2_400
#: Past this a quadratic run would take minutes: the check must have failed before.
_SLOW_SIZE = 20_000
#: The one size at which the hiccup below strikes.
_HICCUP_SIZE = 2 * _TIMED_SIZE
#: The CPU seconds one unit of work is charged: a linear run on the largest timed size
#: (24 million units) takes 0.24 s, a quadratic one on the largest quadratic size 0.92 s.
_SECONDS_PER_UNIT = 1e-8


@final
class _FakeTime:
    """The thread's CPU clock, advanced only by the work a case charges to it."""

    __slots__ = ("now",)

    def __init__(self) -> None:
        self.now = 0.0

    def thread_time(self) -> float:
        return self.now

    def charge(self, units: int) -> None:
        self.now += units * _SECONDS_PER_UNIT


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _FakeTime:
    """Put the fake clock in place of the ``time`` module the check reads."""
    fake = _FakeTime()
    monkeypatch.setattr(growth, "time", fake)
    return fake


def _linear(clock: _FakeTime) -> Callable[[int], int]:
    def run(size: int) -> int:
        clock.charge(size)
        return size

    return run


def _quadratic(clock: _FakeTime) -> Callable[[int], int]:
    def run(size: int) -> int:
        clock.charge(size * size)
        return size

    return run


def _quadratic_until_slow(clock: _FakeTime) -> Callable[[int], int]:
    def run(size: int) -> int:
        if size > _SLOW_SIZE:
            msg = f"the check ran a quadratic cost on {size}"
            raise RuntimeError(msg)
        clock.charge(size * size)
        return size

    return run


def _linear_with_a_hiccup(clock: _FakeTime) -> Callable[[int], int]:
    """A linear cost whose every run at one size is slowed, as a busy machine may do."""

    def run(size: int) -> int:
        clock.charge(size * 3 if size == _HICCUP_SIZE else size)
        return size

    return run


def test_a_linear_cost_passes(clock: _FakeTime) -> None:
    _ = assert_linear_growth(_linear(clock), _TIMED_SIZE)


def test_a_linear_cost_too_quick_to_time_passes(clock: _FakeTime) -> None:
    _ = assert_linear_growth(_linear(clock), 1_000)


def test_one_slowed_step_passes(clock: _FakeTime) -> None:
    _ = assert_linear_growth(_linear_with_a_hiccup(clock), _TIMED_SIZE)


def test_a_quadratic_cost_fails(clock: _FakeTime) -> None:
    with pytest.raises(AssertionError, match="4x the input took"):
        _ = assert_linear_growth(_quadratic(clock), _QUADRATIC_SIZE)


def test_a_quadratic_cost_fails_before_the_large_input_runs(clock: _FakeTime) -> None:
    with pytest.raises(AssertionError, match="4x the input took"):
        _ = assert_linear_growth(_quadratic_until_slow(clock), 64 * _QUADRATIC_SIZE)


def test_only_the_threads_cpu_clock_is_read(clock: _FakeTime) -> None:
    """Time spent waiting is not counted: the check reads the thread's CPU clock and no other.

    The fake ``time`` carries ``thread_time`` alone, so a check reading a wall clock would
    raise here instead of measuring how long a busy machine kept this thread waiting.
    """
    _ = assert_linear_growth(_linear(clock), _TIMED_SIZE)

    assert clock.now > 0


def test_what_the_largest_input_gave_is_returned(clock: _FakeTime) -> None:
    assert assert_linear_growth(_linear(clock), 1_000) == 4_000
