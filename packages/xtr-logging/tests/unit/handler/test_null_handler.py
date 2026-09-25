from __future__ import annotations

from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import Logger, NullHandler, TestHandler


def test_it_stops_records_at_its_level() -> None:
    below = TestHandler()
    logger = Logger("app", [NullHandler(Level.WARNING), below])

    logger.error("swallowed")
    logger.info("passes")

    assert [record.message for record in below.records] == ["passes"]


def test_it_reports_handling_only_at_its_level() -> None:
    handler = NullHandler(Level.ERROR)

    assert handler.handle(make_record(Level.ERROR))
    assert not handler.handle(make_record(Level.INFO))
