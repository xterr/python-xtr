"""The growth check passes a linear cost and fails a quadratic one, at a small size first."""

from __future__ import annotations

import time

import pytest

from tests.support.growth import assert_linear_growth

#: Past this a quadratic run would take minutes: the check must have failed before.
_SLOW_SIZE = 20_000


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
    time.sleep(0.1 * (size / 800_000) ** 2)
    return total


def test_a_linear_cost_passes() -> None:
    _ = assert_linear_growth(_linear, 200_000)


def test_a_quadratic_cost_fails() -> None:
    with pytest.raises(AssertionError, match="4x the input took"):
        _ = assert_linear_growth(_quadratic, 1_000)


def test_a_quadratic_cost_fails_before_the_large_input_runs() -> None:
    with pytest.raises(AssertionError, match="4x the input took"):
        _ = assert_linear_growth(_quadratic_until_slow, 250_000)


def test_time_spent_waiting_is_not_counted() -> None:
    _ = assert_linear_growth(_linear_then_waiting, 200_000)


def test_what_the_largest_input_gave_is_returned() -> None:
    assert assert_linear_growth(_linear, 1_000) == sum(range(4_000))
