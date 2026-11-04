"""The growth check passes a linear cost and fails a quadratic one, at a small size first."""

from __future__ import annotations

import time

import pytest

from tests.support.growth import assert_linear_growth

#: Large enough that the last steps of a linear cost take longer than the check's floor.
_TIMED_SIZE = 6_000_000
#: Large enough that the last steps of a quadratic cost take longer than the check's floor.
_QUADRATIC_SIZE = 2_400
#: Past this a quadratic run would take minutes: the check must have failed before.
_SLOW_SIZE = 20_000
#: The one size at which the hiccup below strikes.
_HICCUP_SIZE = 2 * _TIMED_SIZE


def _linear(size: int) -> int:
    return sum(range(size))


def _quadratic(size: int) -> int:
    return sum(range(size * size))


def _quadratic_until_slow(size: int) -> int:
    if size > _SLOW_SIZE:
        msg = f"the check ran a quadratic cost on {size}"
        raise RuntimeError(msg)
    return _quadratic(size)


def _linear_then_waiting(size: int) -> int:
    total = _linear(size)
    time.sleep(0.4 * (size / (4 * _TIMED_SIZE)) ** 2)
    return total


def _linear_with_a_hiccup(size: int) -> int:
    """A linear cost whose every run at one size is slowed, as a busy machine may do."""
    return _linear(size * 3 if size == _HICCUP_SIZE else size)


def test_a_linear_cost_passes() -> None:
    _ = assert_linear_growth(_linear, _TIMED_SIZE)


def test_a_linear_cost_too_quick_to_time_passes() -> None:
    _ = assert_linear_growth(_linear, 1_000)


def test_one_slowed_step_passes() -> None:
    _ = assert_linear_growth(_linear_with_a_hiccup, _TIMED_SIZE)


def test_a_quadratic_cost_fails() -> None:
    with pytest.raises(AssertionError, match="4x the input took"):
        _ = assert_linear_growth(_quadratic, _QUADRATIC_SIZE)


def test_a_quadratic_cost_fails_before_the_large_input_runs() -> None:
    with pytest.raises(AssertionError, match="4x the input took"):
        _ = assert_linear_growth(_quadratic_until_slow, 64 * _QUADRATIC_SIZE)


def test_time_spent_waiting_is_not_counted() -> None:
    _ = assert_linear_growth(_linear_then_waiting, _TIMED_SIZE)


def test_what_the_largest_input_gave_is_returned() -> None:
    assert assert_linear_growth(_linear, 1_000) == sum(range(4_000))
