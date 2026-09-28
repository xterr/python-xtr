from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import AbstractHandler, LogRecord


@final
class Counting(AbstractHandler):
    """Counts the records handed to it one at a time."""

    def __init__(self, level: Level = Level.DEBUG) -> None:
        super().__init__(level)
        self.handled: list[str] = []

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.handled.append(record.message)
        return False


def test_it_handles_records_at_its_level_or_above() -> None:
    handler = Counting(Level.WARNING)

    assert handler.is_handling(make_record(Level.WARNING))
    assert not handler.is_handling(make_record(Level.INFO))


def test_a_new_level_takes_effect_at_once() -> None:
    handler = Counting(Level.ERROR)

    handler.set_level("debug")

    assert handler.is_handling(make_record(Level.DEBUG))


def test_a_batch_is_handled_one_record_at_a_time_by_default() -> None:
    handler = Counting()

    handler.handle_batch([make_record(message="a"), make_record(message="b")])

    assert handler.handled == ["a", "b"]


def test_it_bubbles_unless_told_otherwise() -> None:
    assert Counting().bubble is True
