from __future__ import annotations

import random
from typing import final

import pytest
from typing_extensions import override

from tests.support.records import make_record
from xtr_logging import InvalidOptionError, Level, LogRecord, TestHandler
from xtr_logging.handler.sampling_handler import SamplingHandler


@final
class FixedRandom(random.Random):
    """A random source whose draw is fixed, so sampling is deterministic."""

    def __init__(self, value: int) -> None:
        super().__init__()
        self._value = value

    @override
    def randint(self, a: int, b: int) -> int:
        return self._value


def _stamp(record: LogRecord, /) -> LogRecord:
    return record.with_extra({"stamped": True})


def test_it_forwards_when_the_draw_hits() -> None:
    member = TestHandler()
    handler = SamplingHandler(member, 3, rng=FixedRandom(1))

    _ = handler.handle(make_record())

    assert len(member.records) == 1


def test_it_drops_when_the_draw_misses() -> None:
    member = TestHandler()
    handler = SamplingHandler(member, 3, rng=FixedRandom(2))

    _ = handler.handle(make_record())

    assert member.records == ()


def test_a_factor_of_one_keeps_every_record() -> None:
    member = TestHandler()
    handler = SamplingHandler(member, 1)

    for _ in range(5):
        _ = handler.handle(make_record())

    assert len(member.records) == 5


def test_a_factor_below_one_is_refused() -> None:
    with pytest.raises(InvalidOptionError):
        _ = SamplingHandler(TestHandler(), 0)


def test_is_handling_delegates_to_the_wrapped_handler() -> None:
    handler = SamplingHandler(TestHandler(Level.ERROR), 2)

    assert handler.is_handling(make_record(Level.ERROR))
    assert not handler.is_handling(make_record(Level.INFO))


def test_about_one_in_factor_survive_over_many_records() -> None:
    member = TestHandler()
    handler = SamplingHandler(member, 4, rng=random.Random(20260924))  # noqa: S311 — deterministic sampling in a test

    for _ in range(2000):
        _ = handler.handle(make_record())

    assert 400 <= len(member.records) <= 600


def test_its_processors_run_before_forwarding() -> None:
    member = TestHandler()
    handler = SamplingHandler(member, 1, rng=FixedRandom(1))
    handler.push_processor(_stamp)

    _ = handler.handle(make_record())

    assert member.records[0].extra["stamped"] is True


def test_a_sampled_record_still_bubbles() -> None:
    handler = SamplingHandler(TestHandler(), 1, rng=FixedRandom(1))

    assert not handler.handle(make_record())
