from __future__ import annotations

import re

from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import LogRecord, TestHandler


def _handler_with(*records: LogRecord) -> TestHandler:
    handler = TestHandler()
    for record in records:
        _ = handler.handle(record)
    return handler


def test_it_keeps_records_in_order() -> None:
    first, second = make_record(message="one"), make_record(message="two")

    assert _handler_with(first, second).records == (first, second)


def test_it_keeps_the_formatted_text() -> None:
    handler = _handler_with(make_record(Level.ERROR, "boom", channel="db"))

    assert handler.formatted[0].startswith("[2026-09-24T12:30:45.123456+00:00] db.ERROR: boom")


def test_has_records_matches_the_exact_level() -> None:
    handler = _handler_with(make_record(Level.ERROR))

    assert handler.has_records(Level.ERROR)
    assert not handler.has_records("critical")


def test_has_record_matches_message_and_optionally_context() -> None:
    handler = _handler_with(make_record(Level.INFO, "saved", context={"id": 1}))

    assert handler.has_record("saved", Level.INFO)
    assert handler.has_record("saved", Level.INFO, {"id": 1})
    assert not handler.has_record("saved", Level.INFO, {"id": 2})


def test_has_record_that_contains_matches_a_fragment() -> None:
    handler = _handler_with(make_record(Level.WARNING, "disk almost full"))

    assert handler.has_record_that_contains("almost", "warning")


def test_has_record_that_matches_searches_with_a_pattern() -> None:
    handler = _handler_with(make_record(Level.INFO, "user 42 logged in"))

    assert handler.has_record_that_matches(r"user \d+", Level.INFO)
    assert handler.has_record_that_matches(re.compile("logged"), Level.INFO)
    assert not handler.has_record_that_matches("^logged", Level.INFO)


def test_has_record_that_passes_applies_a_predicate() -> None:
    handler = _handler_with(make_record(Level.DEBUG, context={"n": 3}))

    assert handler.has_record_that_passes(lambda r: r.context.get("n") == 3, Level.DEBUG)


def test_clear_and_reset_forget_everything() -> None:
    handler = _handler_with(make_record())

    handler.reset()

    assert handler.records == ()
    assert handler.formatted == ()


def test_pytest_does_not_collect_it_as_a_test_class() -> None:
    assert TestHandler.__test__ is False
