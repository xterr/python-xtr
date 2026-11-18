from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from xtr_stopwatch import EventNotStartedError, StopwatchEvent
from xtr_stopwatch._milliseconds import now_ms

if TYPE_CHECKING:
    from xtr_clock import MockClock


def _event(clock: MockClock, category: str | None = None) -> StopwatchEvent:
    return StopwatchEvent(now_ms(clock), category, "load", clock)


def test_a_stopped_event_has_one_period_from_its_origin(clock: MockClock) -> None:
    event = _event(clock)
    clock.sleep(0.002)

    _ = event.start()
    clock.sleep(0.005)
    _ = event.stop()

    (period,) = event.get_periods()
    assert period.start == pytest.approx(2.0)
    assert period.duration == pytest.approx(5.0)


def test_each_run_adds_a_period_and_the_duration_sums_them(clock: MockClock) -> None:
    event = _event(clock)

    for _ in range(3):
        _ = event.start()
        clock.sleep(0.001)
        _ = event.stop()
        clock.sleep(0.010)

    assert len(event.get_periods()) == 3
    assert event.get_duration() == pytest.approx(3.0)
    assert event.get_start_time() == pytest.approx(0.0)
    assert event.get_end_time() == pytest.approx(23.0)


def test_a_running_event_counts_up_to_now(clock: MockClock) -> None:
    event = _event(clock).start()
    clock.sleep(0.004)

    assert event.is_started()
    assert event.get_duration() == pytest.approx(4.0)
    assert event.get_start_time() == pytest.approx(0.0)
    assert event.get_end_time() == 0.0


def test_a_never_started_event_reads_zero(clock: MockClock) -> None:
    event = _event(clock)

    assert event.get_start_time() == 0.0
    assert event.get_duration() == 0.0


def test_stopping_an_event_that_is_not_running_is_refused(clock: MockClock) -> None:
    with pytest.raises(EventNotStartedError, match='event "load" is not started') as caught:
        _ = _event(clock).stop()

    assert caught.value.name == "load"


def test_a_lap_closes_one_period_and_opens_the_next(clock: MockClock) -> None:
    event = _event(clock).start()
    clock.sleep(0.001)

    _ = event.lap()
    clock.sleep(0.002)
    _ = event.stop()

    assert [period.duration for period in event.get_periods()] == pytest.approx([1.0, 2.0])


def test_ensure_stopped_closes_every_open_period(clock: MockClock) -> None:
    event = _event(clock).start().start()

    event.ensure_stopped()

    assert not event.is_started()
    assert len(event.get_periods()) == 2


def test_the_category_defaults(clock: MockClock) -> None:
    assert _event(clock).category == "default"
    assert _event(clock, "orm").category == "orm"


def test_an_event_without_a_name_or_clock_still_times() -> None:
    event = StopwatchEvent(0.0)

    assert event.name == "unknown"
    assert event.start().stop().get_duration() >= 0.0


def test_an_event_is_plain_data(clock: MockClock) -> None:
    event = _event(clock, "orm")
    origin = event.origin
    _ = event.start()
    clock.sleep(0.003)
    _ = event.stop()

    data = event.to_dict()

    assert json.loads(json.dumps(data)) == data
    assert data["name"] == "load"
    assert data["category"] == "orm"
    assert data["origin"] == origin
    assert data["duration"] == pytest.approx(3.0)
    assert data["periods"] == [period.to_dict() for period in event.get_periods()]


def test_an_event_shows_its_name_category_and_duration(clock: MockClock) -> None:
    assert repr(_event(clock)) == "StopwatchEvent('load', category='default', duration=0.000)"
