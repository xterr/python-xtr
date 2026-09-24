from __future__ import annotations

from tests.support.records import make_record
from xtr_logging import Level
from xtr_logging.formatter.json_batch_mode import JsonBatchMode
from xtr_logging.formatter.json_formatter import JsonFormatter


def test_it_renders_the_record_as_one_object() -> None:
    # Given a record with context but no extra
    record = make_record(Level.WARNING, "low disk", channel="ops", context={"free": 3})

    # When it is formatted with the defaults
    # Then the keys appear in a fixed order, level as its number, time as ISO 8601
    assert JsonFormatter().format(record) == (
        '{"message":"low disk","context":{"free":3},"level":300,"level_name":"WARNING",'
        '"channel":"ops","datetime":"2026-09-24T12:30:45.123456+00:00","extra":{}}\n'
    )


def test_a_newline_can_be_left_off() -> None:
    assert not JsonFormatter(append_newline=False).format(make_record()).endswith("\n")


def test_empty_context_and_extra_can_be_omitted() -> None:
    formatter = JsonFormatter(ignore_empty_context_and_extra=True, append_newline=False)

    assert formatter.format(make_record()) == (
        '{"message":"something happened","level":200,"level_name":"INFO",'
        '"channel":"app","datetime":"2026-09-24T12:30:45.123456+00:00"}'
    )


def test_extra_is_rendered_when_present() -> None:
    formatter = JsonFormatter(append_newline=False)
    record = make_record(extra={"uid": "x1"})

    assert '"extra":{"uid":"x1"}' in formatter.format(record)


def test_an_exception_becomes_the_normalisers_structure() -> None:
    formatter = JsonFormatter(append_newline=False)
    record = make_record(context={"exception": ValueError("bad")})

    assert '"exception":{"class":"ValueError","message":"bad"' in formatter.format(record)


def test_a_date_format_shapes_the_timestamp() -> None:
    formatter = JsonFormatter(append_newline=False, date_format="%Y-%m-%d")

    assert '"datetime":"2026-09-24"' in formatter.format(make_record())


def test_a_batch_is_one_json_array_without_inner_newlines() -> None:
    formatter = JsonFormatter(JsonBatchMode.JSON)
    records = [make_record(message="a"), make_record(message="b")]

    batch = formatter.format_batch(records)

    assert batch.startswith('[{"message":"a"')
    assert batch.endswith("}]")
    assert "\n" not in batch


def test_a_newline_batch_puts_one_object_on_each_line() -> None:
    formatter = JsonFormatter(JsonBatchMode.NEWLINES)
    records = [make_record(message="a"), make_record(message="b")]

    lines = formatter.format_batch(records).split("\n")

    assert len(lines) == 2
    assert lines[0].startswith('{"message":"a"')
    assert lines[1].startswith('{"message":"b"')
