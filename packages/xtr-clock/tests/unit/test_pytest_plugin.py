from __future__ import annotations

import time

from xtr_clock import Clock, DatePoint, MockClock, SystemClock, now


def test_it_hands_a_test_a_frozen_clock(clock: MockClock) -> None:
    assert isinstance(clock, MockClock)


def test_the_clock_it_hands_over_is_the_one_in_force(clock: MockClock) -> None:
    assert Clock.get() is clock


def test_time_does_not_pass_while_a_test_holds_it(clock: MockClock) -> None:
    first = now()
    time.sleep(0.01)

    assert now() == first == clock.now()


def test_the_clock_it_hands_over_can_be_moved_forward(clock: MockClock) -> None:
    first = now()

    clock.sleep(3600)

    assert (now() - first).total_seconds() == 3600


def test_it_reaches_code_that_reads_the_instant_directly(clock: MockClock) -> None:
    assert DatePoint.now() == clock.now()


def test_it_freezes_in_utc_so_the_answer_does_not_depend_on_the_machine(
    clock: MockClock,
) -> None:
    assert clock.now().utcoffset() is not None
    assert clock.now().strftime("%z") == "+0000"


def test_a_test_that_never_asks_for_it_is_left_alone() -> None:
    assert isinstance(Clock.get(), SystemClock)
