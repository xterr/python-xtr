"""The growth check passes a linear cost and fails a quadratic one."""

from __future__ import annotations

import pytest

from tests.support.growth import assert_linear_growth


def _linear(size: int) -> int:
    return sum(range(size))


def _quadratic(size: int) -> int:
    return sum(range(size * size))


def test_a_linear_cost_passes() -> None:
    assert_linear_growth(_linear, 200_000)


def test_a_quadratic_cost_fails() -> None:
    with pytest.raises(AssertionError, match="4x the input took"):
        assert_linear_growth(_quadratic, 1_000)
