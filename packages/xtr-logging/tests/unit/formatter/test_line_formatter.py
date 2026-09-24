from __future__ import annotations

import re

from tests.support.records import make_record
from xtr_logging import Level, LineFormatter


def _raise(error: Exception) -> None:
    raise error


def _raised(error: Exception) -> Exception:
    try:
        _raise(error)
    except Exception as caught:  # noqa: BLE001 — the point is to capture a traceback
        return caught
    raise AssertionError


def test_the_default_format() -> None:
    record = make_record(Level.WARNING, "low disk", channel="ops", context={"free": 3})

    assert LineFormatter().format(record) == (
        '[2026-09-24T12:30:45.123456+00:00] ops.WARNING: low disk {"free":3} []\n'
    )


def test_empty_context_and_extra_print_as_empty_lists() -> None:
    assert LineFormatter("%context% %extra%").format(make_record()) == "[] []"


def test_empty_context_and_extra_can_be_left_out() -> None:
    formatter = LineFormatter(ignore_empty_context_and_extra=True)

    assert formatter.format(make_record(message="hi")).endswith("app.INFO: hi\n")


def test_every_simple_token_is_substituted() -> None:
    formatter = LineFormatter("%datetime%|%channel%|%level_name%|%level%|%message%", "%H:%M")

    assert formatter.format(make_record(Level.ERROR, "boom")) == "12:30|app|ERROR|400|boom"


def test_a_keyed_token_prints_one_entry_and_removes_it_from_the_bag() -> None:
    record = make_record(context={"user": "ana", "id": 1}, extra={"uid": "x1"})

    rendered = LineFormatter("%extra.uid% %context.user% %context% %extra%").format(record)

    assert rendered == 'x1 ana {"id":1} []'


def test_a_keyed_token_for_a_missing_entry_is_dropped() -> None:
    assert LineFormatter("[%context.missing%]").format(make_record()) == "[]"


def test_line_breaks_in_values_become_spaces() -> None:
    rendered = LineFormatter("%message%").format(make_record(message="one\ntwo\r\nthree"))

    assert rendered == "one two three"


def test_line_breaks_are_kept_when_allowed() -> None:
    formatter = LineFormatter("%message%", allow_inline_line_breaks=True)

    assert formatter.format(make_record(message="one\ntwo")) == "one\ntwo"


def test_an_exception_prints_its_class_message_and_origin() -> None:
    record = make_record(context={"exception": _raised(ValueError("bad"))})

    rendered = LineFormatter("%context%").format(record)

    assert rendered.startswith('{"exception":"[object] (ValueError: bad at ')
    assert re.search(r"test_line_formatter\.py:\d+\)", rendered)


def test_a_chained_exception_prints_its_cause() -> None:
    error = RuntimeError("outer")
    error.__cause__ = KeyError("inner")

    rendered = LineFormatter("%context.exception%").format(
        make_record(context={"exception": error})
    )

    assert (
        rendered
        == "[object] (RuntimeError: outer) [previous exception] [object] (KeyError: 'inner')"
    )


def test_stack_traces_are_printed_on_request() -> None:
    record = make_record(context={"exception": _raised(ValueError("bad"))})

    rendered = LineFormatter("%context.exception%", include_stacktraces=True).format(record)

    assert "\n[stacktrace]\n" in rendered
    assert "_raise(error)" in rendered


def test_a_batch_is_the_records_joined() -> None:
    formatter = LineFormatter("%message%\n")

    assert formatter.format_batch([make_record(message="a"), make_record(message="b")]) == "a\nb\n"


def test_unicode_is_kept_as_written() -> None:
    assert (
        LineFormatter("%context%").format(make_record(context={"city": "Brașov"}))
        == '{"city":"Brașov"}'
    )


def test_an_ignored_empty_bag_leaves_no_gap_between_its_neighbours() -> None:
    formatter = LineFormatter("%message% %context% %extra%", ignore_empty_context_and_extra=True)

    assert formatter.format(make_record(message="hi", extra={"a": 1})) == 'hi {"a":1}'
