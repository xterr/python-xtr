"""How time grows with input size, checked without a wall-clock budget.

A fixed budget in seconds trips on a loaded machine and passes a slow algorithm on a fast one.
Comparing an input four times larger against a smaller one holds under any load: a linear cost
takes about four times as long, a quadratic one sixteen. The best of a few runs is kept for
each size, so one run slowed by the machine does not decide.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["assert_linear_growth"]

_FACTOR: Final = 4
_GROWTH_LIMIT: Final = 10.0
_RUNS: Final = 3
#: Below this a measurement is mostly the timer's own noise.
_FLOOR_SECONDS: Final = 0.001


def assert_linear_growth(run: Callable[[int], object], size: int) -> None:
    """Assert ``run`` on four times ``size`` takes under ten times as long as on ``size``."""
    small = _best_of(run, size)
    large = _best_of(run, _FACTOR * size)

    assert large < max(small, _FLOOR_SECONDS) * _GROWTH_LIMIT, (
        f"{_FACTOR}x the input took {large:.4f}s against {small:.4f}s"
    )


def _best_of(run: Callable[[int], object], size: int) -> float:
    timings: list[float] = []
    for _ in range(_RUNS):
        started = time.perf_counter()
        _ = run(size)
        timings.append(time.perf_counter() - started)
    return min(timings)
