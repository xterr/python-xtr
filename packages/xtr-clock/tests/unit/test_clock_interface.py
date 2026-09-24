from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from xtr_clock import (
    Clock,
    ClockInterface,
    MockClock,
    MonotonicClock,
    SupportsNow,
    SystemClock,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class NowOnly:
    def now(self) -> datetime:
        return datetime(2001, 9, 9, 1, 46, 40, tzinfo=UTC)


class NotAClock:
    def tick(self) -> None: ...


CLOCKS: list[Callable[[], object]] = [
    SystemClock,
    MonotonicClock,
    MockClock,
    lambda: Clock(NowOnly()),
]


@pytest.mark.parametrize("build", CLOCKS)
def test_every_clock_in_this_library_satisfies_the_full_contract(
    build: Callable[[], object],
) -> None:
    assert isinstance(build(), ClockInterface)


@pytest.mark.parametrize("build", CLOCKS)
def test_every_clock_in_this_library_can_also_just_say_the_time(
    build: Callable[[], object],
) -> None:
    assert isinstance(build(), SupportsNow)


def test_an_object_that_only_says_the_time_satisfies_the_smaller_contract() -> None:
    assert isinstance(NowOnly(), SupportsNow)


def test_an_object_that_only_says_the_time_does_not_satisfy_the_full_contract() -> None:
    assert not isinstance(NowOnly(), ClockInterface)


def test_an_object_that_cannot_say_the_time_satisfies_neither() -> None:
    assert not isinstance(NotAClock(), SupportsNow)
    assert not isinstance(NotAClock(), ClockInterface)


def test_the_full_contract_is_a_narrowing_of_the_smaller_one() -> None:
    assert issubclass(ClockInterface, SupportsNow)
