from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from enum import Enum

from tests.support.records import make_record
from xtr_logging.processor.placeholder_processor import PlaceholderProcessor


def test_a_message_without_a_brace_is_returned_untouched() -> None:
    # Given a message that holds no placeholder
    processor = PlaceholderProcessor()
    record = make_record(message="nothing to fill")

    # When it is processed
    # Then the very same record comes back, unexamined
    assert processor(record) is record


def test_a_placeholder_is_filled_from_the_context() -> None:
    # Given a message with a placeholder and a matching context key
    processor = PlaceholderProcessor()
    record = make_record(message="user {id} signed in", context={"id": 7})

    # When it is processed
    # Then the placeholder is replaced by the value
    assert processor(record).message == "user 7 signed in"


def test_a_placeholder_with_no_matching_key_is_left_as_written() -> None:
    # Given a placeholder no context key answers
    processor = PlaceholderProcessor()
    record = make_record(message="hello {name}", context={"id": 7})

    # When it is processed
    # Then the placeholder is left exactly as written
    assert processor(record).message == "hello {name}"


def test_none_renders_as_null() -> None:
    processor = PlaceholderProcessor()
    record = make_record(message="value is {v}", context={"v": None})

    assert processor(record).message == "value is null"


def test_booleans_render_as_true_and_false() -> None:
    processor = PlaceholderProcessor()
    record = make_record(message="{yes} {no}", context={"yes": True, "no": False})

    assert processor(record).message == "true false"


def test_a_string_is_kept_as_written() -> None:
    processor = PlaceholderProcessor()
    record = make_record(message="{who}", context={"who": "ana"})

    assert processor(record).message == "ana"


def test_numbers_and_objects_with_their_own_text_use_it() -> None:
    # Given values whose classes render themselves
    processor = PlaceholderProcessor()
    record = make_record(
        message="{n} {price} {id}",
        context={"n": 42, "price": Decimal("9.99"), "id": uuid.UUID(int=0)},
    )

    # When they are interpolated
    # Then each is rendered by its own str()
    assert processor(record).message == "42 9.99 00000000-0000-0000-0000-000000000000"


def test_a_datetime_uses_the_given_format() -> None:
    processor = PlaceholderProcessor("%Y-%m-%d")
    at = dt.datetime(2026, 9, 24, tzinfo=dt.UTC)
    record = make_record(message="on {day}", context={"day": at})

    assert processor(record).message == "on 2026-09-24"


def test_a_datetime_without_a_format_is_iso_8601() -> None:
    processor = PlaceholderProcessor()
    at = dt.datetime(2026, 9, 24, 12, 0, tzinfo=dt.UTC)
    record = make_record(message="at {t}", context={"t": at})

    assert processor(record).message == "at 2026-09-24T12:00:00+00:00"


def test_an_enum_renders_as_its_value() -> None:
    class Colour(Enum):
        RED = "red"

    processor = PlaceholderProcessor()
    record = make_record(message="{c}", context={"c": Colour.RED})

    assert processor(record).message == "red"


def test_a_collection_renders_as_array_and_json() -> None:
    processor = PlaceholderProcessor()
    record = make_record(message="{items}", context={"items": [1, 2]})

    assert processor(record).message == "array[1,2]"


def test_an_exception_renders_as_its_class_and_message() -> None:
    processor = PlaceholderProcessor()
    record = make_record(message="{err}", context={"err": ValueError("boom")})

    assert processor(record).message == "ValueError: boom"


def test_an_object_without_its_own_text_names_its_class() -> None:
    class Widget:
        pass

    processor = PlaceholderProcessor()
    record = make_record(message="{w}", context={"w": Widget()})

    message = processor(record).message
    assert message.startswith("[object ")
    assert message.endswith(".Widget]")


def test_used_context_fields_can_be_removed() -> None:
    # Given the processor is told to drop substituted keys
    processor = PlaceholderProcessor(remove_used_context_fields=True)
    record = make_record(message="user {id}", context={"id": 7, "keep": "yes"})

    # When a key is used in the message
    result = processor(record)

    # Then it is gone from the context, but untouched keys remain
    assert result.message == "user 7"
    assert dict(result.context) == {"keep": "yes"}


def test_used_context_fields_are_kept_by_default() -> None:
    processor = PlaceholderProcessor()
    record = make_record(message="user {id}", context={"id": 7})

    assert dict(processor(record).context) == {"id": 7}
