from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from tests.support.records import make_record
from xtr_logging import AbstractHandler, LogRecord, TestHandler
from xtr_logging.handler.fallback_group_handler import FallbackGroupHandler

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
class Boom(AbstractHandler):
    """A member that always fails, with a label so the failure is identifiable."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    @override
    def handle(self, record: LogRecord, /) -> bool:
        raise RuntimeError(self.label)

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        raise RuntimeError(self.label)


def test_it_stops_at_the_first_member_that_succeeds() -> None:
    first, second = TestHandler(), TestHandler()
    group = FallbackGroupHandler([first, second])

    _ = group.handle(make_record())

    assert len(first.records) == 1
    assert second.records == ()


def test_it_falls_through_to_the_next_when_one_fails() -> None:
    survivor = TestHandler()
    group = FallbackGroupHandler([Boom("down"), survivor])

    _ = group.handle(make_record())

    assert len(survivor.records) == 1


def test_it_reraises_the_last_failure_when_every_member_fails() -> None:
    group = FallbackGroupHandler([Boom("first"), Boom("second")])

    with pytest.raises(RuntimeError, match="second"):
        _ = group.handle(make_record())


def test_handle_batch_stops_at_the_first_member_that_succeeds() -> None:
    first, second = TestHandler(), TestHandler()
    group = FallbackGroupHandler([first, second])

    group.handle_batch([make_record(message="a")])

    assert [record.message for record in first.records] == ["a"]
    assert second.records == ()


def test_handle_batch_reraises_the_last_failure_when_every_member_fails() -> None:
    group = FallbackGroupHandler([Boom("first"), Boom("second")])

    with pytest.raises(RuntimeError, match="second"):
        group.handle_batch([make_record()])


def test_bubble_off_stops_the_record() -> None:
    assert FallbackGroupHandler([TestHandler()], bubble=False).handle(make_record())
