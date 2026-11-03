"""How the CPU time a call takes grows with its input, checked without a budget in seconds.

A fixed budget trips on a loaded machine and passes a slow algorithm on a fast one. What is
compared instead is the CPU time this thread spent on an input four times larger against a
smaller one: a linear cost takes about four times as long, a quadratic one sixteen. Time the
thread spends waiting — for a core another process holds, or sleeping — is not counted, so the
check holds however busy the machine is; the call must do its work on this thread.

The sizes climb four-fold from a small one up to four times the size given, each step checked
against the one before: a quadratic cost fails at a size it takes milliseconds on, before the
large input — which it would take minutes on — ever runs. The best of a few runs is kept for
each size, so one run slowed by the machine does not decide.
"""

from __future__ import annotations

import time
from itertools import pairwise
from typing import TYPE_CHECKING, Final, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["assert_linear_growth"]

_T = TypeVar("_T")

_FACTOR: Final = 4
_STEPS: Final = 5
_GROWTH_LIMIT: Final = 10.0
_RUNS: Final = 3
#: Below this a measurement is mostly the timer's own noise.
_FLOOR_SECONDS: Final = 0.001


def assert_linear_growth(run: Callable[[int], _T], size: int) -> _T:
    """Assert each four-fold step up to four times ``size`` takes under ten times the one before.

    Returns:
        What ``run`` gave on four times ``size``, so a test checks the large input only once
        its growth held.
    """
    sizes = [_FACTOR * size]
    for _ in range(_STEPS):
        sizes.insert(0, sizes[0] // _FACTOR)
    result, before = _best_of(run, sizes[0])
    for smaller, larger in pairwise(sizes):
        result, taken = _best_of(run, larger)
        assert taken < max(before, _FLOOR_SECONDS) * _GROWTH_LIMIT, (
            f"{_FACTOR}x the input took {taken:.4f}s against {before:.4f}s ({larger} against "
            f"{smaller})"
        )
        before = taken
    return result


def _best_of(run: Callable[[int], _T], size: int) -> tuple[_T, float]:
    result, best = _timed(run, size)
    for _ in range(_RUNS - 1):
        result, taken = _timed(run, size)
        best = min(best, taken)
    return result, best


def _timed(run: Callable[[int], _T], size: int) -> tuple[_T, float]:
    started = time.thread_time()
    result = run(size)
    return result, time.thread_time() - started
