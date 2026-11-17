from __future__ import annotations

from xtr_stopwatch import StopwatchPeriod


def test_a_period_lasts_from_its_start_to_its_end() -> None:
    period = StopwatchPeriod(2.0, 7.5)

    assert period.duration == 5.5


def test_a_period_is_plain_data() -> None:
    assert StopwatchPeriod(1.0, 3.0).to_dict() == {"start": 1.0, "end": 3.0, "duration": 2.0}


def test_a_period_shows_its_span() -> None:
    assert repr(StopwatchPeriod(1.0, 3.0)) == "StopwatchPeriod(start=1.000, end=3.000)"
