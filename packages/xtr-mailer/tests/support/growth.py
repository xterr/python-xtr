"""How the CPU time a call takes grows with its input, checked without a budget in seconds.

A fixed budget trips on a loaded machine and passes a slow algorithm on a fast one. What is
compared instead is the CPU time this thread spent on an input twice as large against the one
before: a linear cost takes about twice as long, a quadratic one four times. Time the thread
spends waiting — for a core another process holds, or sleeping — is not counted, so the check
holds however busy the machine is; the call must do its work on this thread.

CPU time still wavers — a collection of garbage, a slower core, a cache another process emptied —
and most at a few milliseconds, where a fixed cost can also hide the growth. So no step decides
alone:

- a step is compared only once the smaller input takes longer than a floor: the sizes climb
  until it does, and a cost that stays under it at every size is too small to matter;
- each size is timed up to three times, the best kept, with the garbage collector held off;
- a step growing faster than linear fails the check only if the step after it does not undo
  it: when, across the two, four times the input still takes more than nine times as long. A
  quadratic cost grows sixteen-fold across any two steps, while a measurement a hiccup slowed
  makes its own step look slow and the next one fast, and across the two nothing changed.

The sizes double from a thousandth of four times the size given up to it, so a quadratic cost
fails at a size it takes a fraction of a second on, before the large input — which it would take
minutes on — ever runs.
"""

from __future__ import annotations

import gc
import time
from itertools import pairwise
from typing import TYPE_CHECKING, Final, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["assert_linear_growth"]

_T = TypeVar("_T")

_FACTOR: Final = 2
_STEPS: Final = 10
_LARGEST: Final = 4
_GROWTH_LIMIT: Final = 3.0
_RUNS: Final = 3
#: Below this a measurement is mostly the timer's and the machine's noise, or a fixed cost.
_FLOOR_SECONDS: Final = 0.03


def assert_linear_growth(run: Callable[[int], _T], size: int) -> _T:
    """Assert the CPU time of ``run`` grows linearly with its size, up to four times ``size``.

    Returns:
        What ``run`` gave on four times ``size``, so a test checks the large input only once
        its growth held.
    """
    sizes = [_LARGEST * size]
    for _ in range(_STEPS):
        sizes.insert(0, sizes[0] // _FACTOR)
    result, before = _best_of(run, sizes[0], bound=None)
    # The smaller size of the last step that grew faster than linear, and its time.
    slow_step: tuple[int, float] | None = None
    for smaller, larger in pairwise(sizes):
        compared = before >= _FLOOR_SECONDS
        bounds = [before * _GROWTH_LIMIT] if compared else []
        if slow_step is not None:
            bounds.append(slow_step[1] * _GROWTH_LIMIT**2)
        bound = min(bounds, default=None)
        result, taken = _best_of(run, larger, bound=bound)
        if slow_step is not None:
            start, started_in = slow_step
            assert taken < started_in * _GROWTH_LIMIT**2, (
                f"{_FACTOR**2}x the input took {taken:.4f}s against {started_in:.4f}s ({larger} "
                f"against {start}): faster than linear over two steps"
            )
        slow_step = (smaller, before) if compared and taken >= before * _GROWTH_LIMIT else None
        before = taken
    return result


def _best_of(run: Callable[[int], _T], size: int, *, bound: float | None) -> tuple[_T, float]:
    """Time ``run`` on ``size`` up to three times, stopping once a time is under ``bound``.

    With no bound — the step is not compared — all three run: the time may be the base of the
    next step, and a base a hiccup slowed would hide a step that grew too fast.
    """
    result, best = _timed(run, size)
    for _ in range(_RUNS - 1):
        if bound is not None and best < bound:
            break
        result, taken = _timed(run, size)
        best = min(best, taken)
    return result, best


def _timed(run: Callable[[int], _T], size: int) -> tuple[_T, float]:
    collecting = gc.isenabled()
    gc.disable()
    try:
        started = time.thread_time()
        result = run(size)
        return result, time.thread_time() - started
    finally:
        if collecting:
            gc.enable()
