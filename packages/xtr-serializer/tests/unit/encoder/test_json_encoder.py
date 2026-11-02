"""JSON text from plain data and back, refusing what JSON cannot carry exactly."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest
from pydantic_core import from_json

from tests.fixtures.nameless import NamelessThing, names_refused
from xtr_serializer.encoder.json_encoder import JsonEncoder
from xtr_serializer.exception import (
    InvalidArgumentError,
    NotEncodableValueError,
    UnsupportedFormatError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_serializer.normalized_value import NormalizedValue

PLANTED_VALUE = "s3cr3t-t0ken-4f9a"

# 4,310 digits, more than the parser reads, in a run of them no message could hold by chance.
PLANTED_DIGITS = "8106234957"
PLANTED_INTEGER = int(PLANTED_DIGITS * 430) * 10**10 + int(PLANTED_DIGITS)

# The longest integer the parser reads, behind a minus sign. Whether the parser counts the sign
# towards its limit depends on its version; the locked one does.
LONGEST_NEGATIVE_TEXT = "[-" + "9" * 4300 + "]"

# Where a float sits in the data, and how its refusal names that place.
FLOAT_PLACES: list[tuple[Callable[[float], NormalizedValue], str]] = [
    (lambda value: value, ""),
    (lambda value: [1, value], "at '[1]': "),
    (lambda value: {"a": {"b": [0, {"c": value}]}}, "at 'a.b[1].c': "),
]


def nested_lists(depth: int) -> list[NormalizedValue]:
    root: list[NormalizedValue] = []
    current = root
    for _ in range(depth - 1):
        child: list[NormalizedValue] = []
        current.append(child)
        current = child
    return root


def nested_dicts(depth: int) -> dict[str, NormalizedValue]:
    root: dict[str, NormalizedValue] = {}
    current = root
    for _ in range(depth - 1):
        child: dict[str, NormalizedValue] = {}
        current["a"] = child
        current = child
    return root


def parser_reads(text: str) -> bool:
    try:
        from_json(text)
    except ValueError:
        return False
    return True


def test_its_format_is_json() -> None:
    assert JsonEncoder.FORMAT == "json"


@pytest.mark.parametrize(("format_", "expected"), [("json", True), ("JSON", False), ("xml", False)])
def test_it_encodes_only_json(format_: str, expected: bool) -> None:
    assert JsonEncoder().supports_encoding(format_) is expected


@pytest.mark.parametrize(("format_", "expected"), [("json", True), ("JSON", False), ("xml", False)])
def test_it_decodes_only_json(format_: str, expected: bool) -> None:
    assert JsonEncoder().supports_decoding(format_) is expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        0,
        -7,
        10**30,
        1.5,
        -0.25,
        1e300,
        "",
        "text",
        [],
        {},
        [None, True, 1, 2.5, "a", [], {}],
        {"name": "Ada", "tags": ["a", "b"], "address": {"city": "Iasi", "zip": None}},
        [{"a": [{"b": [1.0, {"c": ""}]}]}],
    ],
    ids=repr,
)
def test_it_reads_back_exactly_what_it_wrote(value: NormalizedValue) -> None:
    encoder = JsonEncoder()

    decoded = encoder.decode(encoder.encode(value, "json"), "json")

    assert decoded == value
    assert repr(decoded) == repr(value)


def test_it_writes_compact_text_by_default() -> None:
    assert JsonEncoder().encode({"a": [1, 2], "b": None}, "json") == '{"a":[1,2],"b":null}'


def test_it_writes_keys_in_insertion_order() -> None:
    assert JsonEncoder().encode({"b": 1, "a": 2}, "json") == '{"b":1,"a":2}'


def test_it_reads_keys_in_the_order_of_the_text() -> None:
    decoded = JsonEncoder().decode('{"b": 1, "a": 2}', "json")

    assert isinstance(decoded, dict)
    assert list(decoded) == ["b", "a"]


def test_it_indents_when_asked() -> None:
    text = JsonEncoder().encode({"a": [1]}, "json", {"json_indent": 2})

    assert text == '{\n  "a": [\n    1\n  ]\n}'


def test_it_indents_by_its_default_context() -> None:
    text = JsonEncoder({"json_indent": 4}).encode({"a": 1}, "json")

    assert text == '{\n    "a": 1\n}'


def test_the_call_context_wins_over_the_default_context() -> None:
    text = JsonEncoder({"json_indent": 4}).encode({"a": 1}, "json", {"json_indent": 1})

    assert text == '{\n "a": 1\n}'


def test_the_call_context_can_turn_indenting_back_off() -> None:
    text = JsonEncoder({"json_indent": 4}).encode({"a": 1}, "json", {"json_indent": None})

    assert text == '{"a":1}'


def test_a_default_context_changed_afterwards_does_not_reach_the_encoder() -> None:
    default_context: dict[str, object] = {"json_indent": 2}
    encoder = JsonEncoder(default_context)

    default_context["json_indent"] = None

    assert encoder.encode({"a": 1}, "json") == '{\n  "a": 1\n}'


@pytest.mark.parametrize("indent", [-1, True, "2", 1.5], ids=repr)
def test_it_refuses_an_indent_that_is_not_a_count_of_spaces(indent: object) -> None:
    with pytest.raises(InvalidArgumentError, match="json_indent"):
        _ = JsonEncoder().encode({"a": 1}, "json", {"json_indent": indent})


def test_it_indents_by_ten_spaces_at_most() -> None:
    text = JsonEncoder().encode({"a": 1}, "json", {"json_indent": 10})

    assert text == '{\n          "a": 1\n}'


@pytest.mark.parametrize("indent", [11, 2**64 - 1, 2**64], ids=["11", "2**64-1", "2**64"])
def test_it_refuses_an_indent_wider_than_ten_spaces(indent: int) -> None:
    with pytest.raises(InvalidArgumentError, match="json_indent"):
        _ = JsonEncoder().encode({"a": 1}, "json", {"json_indent": indent})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf], ids=repr)
@pytest.mark.parametrize(("make", "location"), FLOAT_PLACES, ids=["root", "list", "nested"])
def test_it_refuses_a_float_json_has_no_form_for(
    value: float,
    make: Callable[[float], NormalizedValue],
    location: str,
) -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().encode(make(value), "json")

    assert str(raised.value) == f"{location}Input should be a finite number [type=finite_number]"


@pytest.mark.parametrize(
    ("value", "location"),
    [({1: "x"}, ""), ({None: 1}, ""), ({"a": [{True: 1}]}, "at 'a[0]': ")],
    ids=["int", "none", "nested-bool"],
)
def test_it_refuses_a_key_that_is_not_a_string(value: object, location: str) -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        # Data that is not plain data is the case under test.
        _ = JsonEncoder().encode(value, "json")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    assert str(raised.value) == (
        f"{location}a key: Input should be a valid string [type=string_type]"
    )


@pytest.mark.parametrize(
    ("value", "location"),
    [((1, 2), ""), ({1, 2}, ""), (b"raw", ""), ({"a": [object()]}, "at 'a[0]': ")],
    ids=["tuple", "set", "bytes", "object"],
)
def test_it_refuses_a_value_that_is_not_plain_data(value: object, location: str) -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        # Data that is not plain data is the case under test.
        _ = JsonEncoder().encode(value, "json")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    assert str(raised.value) == (
        f"{location}input was not a valid JSON value [type=invalid-json-value]"
    )


@pytest.mark.parametrize(
    "value",
    [
        {"token": (PLANTED_VALUE,)},
        {"token": PLANTED_VALUE, "ratio": math.nan},
        {PLANTED_VALUE.encode(): 1},
        {"a": {(PLANTED_VALUE,): 1}},
    ],
    ids=["refused-value", "beside-a-refused-value", "refused-key", "nested-refused-key"],
)
def test_its_refusal_never_quotes_the_data(value: object) -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        # Data that is not plain data is the case under test.
        _ = JsonEncoder().encode(value, "json")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    assert PLANTED_VALUE not in str(raised.value)


def test_its_refusal_chains_no_exception_that_holds_the_data() -> None:
    refused: object = {"token": (PLANTED_VALUE,)}

    with pytest.raises(NotEncodableValueError) as raised:
        # Data that is not plain data is the case under test.
        _ = JsonEncoder().encode(refused, "json")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_it_refuses_to_write_a_string_with_no_utf8_form() -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().encode({"name": f"\ud800{PLANTED_VALUE}"}, "json")

    assert "UTF-8" in str(raised.value)
    assert PLANTED_VALUE not in str(raised.value)
    assert raised.value.__context__ is None


def test_it_refuses_to_read_text_with_no_utf8_form() -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().decode(f'"\ud800{PLANTED_VALUE}"', "json")

    assert "UTF-8" in str(raised.value)
    assert PLANTED_VALUE not in str(raised.value)
    assert raised.value.__context__ is None


def test_it_refuses_to_read_what_is_not_text() -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        # Data that is not text is the case under test.
        _ = JsonEncoder().decode(12, "json")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    assert str(raised.value) == "only str or bytes can be read, not 'int'"
    assert raised.value.__context__ is None


def test_it_names_what_is_not_text_without_running_its_metaclass() -> None:
    with names_refused(), pytest.raises(NotEncodableValueError) as raised:
        # Data that is not text is the case under test.
        _ = JsonEncoder().decode(NamelessThing(), "json")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    assert str(raised.value) == "only str or bytes can be read, not 'NamelessThing'"


def test_it_refuses_data_that_contains_itself() -> None:
    looped: list[NormalizedValue] = []
    looped.append(looped)

    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().encode(looped, "json")

    assert str(raised.value).startswith("at '[0]': ")
    assert str(raised.value).endswith(" [type=recursion_loop]")


@pytest.mark.parametrize("nest", [nested_lists, nested_dicts], ids=["lists", "dicts"])
def test_it_reads_back_nesting_as_deep_as_it_reads(nest: Callable[[int], NormalizedValue]) -> None:
    encoder = JsonEncoder()
    value = nest(201)

    assert encoder.decode(encoder.encode(value, "json"), "json") == value


@pytest.mark.parametrize("depth", [202, 255])
@pytest.mark.parametrize("nest", [nested_lists, nested_dicts], ids=["lists", "dicts"])
def test_it_refuses_to_write_nesting_deeper_than_it_reads(
    nest: Callable[[int], NormalizedValue], depth: int
) -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().encode(nest(depth), "json")

    assert str(raised.value) == "the JSON written would not read back: recursion limit exceeded"
    assert raised.value.__context__ is None


@pytest.mark.parametrize("nest", [nested_lists, nested_dicts], ids=["lists", "dicts"])
def test_it_refuses_nesting_deeper_than_it_checks(nest: Callable[[int], NormalizedValue]) -> None:
    with pytest.raises(NotEncodableValueError, match=r" \[type=recursion_loop\]$"):
        _ = JsonEncoder().encode(nest(256), "json")


def test_it_refuses_to_read_nesting_deeper_than_it_reads() -> None:
    depth = 202

    with pytest.raises(NotEncodableValueError, match="not valid JSON"):
        _ = JsonEncoder().decode("[" * depth + "]" * depth, "json")


@pytest.mark.parametrize(
    "number", [10**4300 - 1, -(10**4299 - 1)], ids=["4300-digits", "minus-4299-digits"]
)
def test_it_reads_back_an_integer_as_long_as_it_reads(number: int) -> None:
    encoder = JsonEncoder()

    assert encoder.decode(encoder.encode([number], "json"), "json") == [number]


@pytest.mark.parametrize(
    "number",
    [10**4300, -(10**4300), 10**5000, PLANTED_INTEGER],
    ids=["4301-digits", "minus-4301-digits", "5001-digits", "4310-digits"],
)
def test_it_refuses_to_write_an_integer_longer_than_it_reads(number: int) -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().encode({"count": [number]}, "json")

    assert str(raised.value) == "the JSON written would not read back: number out of range"
    assert raised.value.__context__ is None


@pytest.mark.skipif(
    parser_reads(LONGEST_NEGATIVE_TEXT), reason="this parser leaves a minus sign out of its limit"
)
def test_it_refuses_a_minus_sign_before_the_longest_integer_where_the_parser_counts_it() -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().encode([-(10**4300 - 1)], "json")

    assert str(raised.value) == "the JSON written would not read back: number out of range"


def test_its_refusal_of_a_long_integer_never_quotes_it() -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().encode(PLANTED_INTEGER, "json")

    assert PLANTED_DIGITS not in str(raised.value)


def test_it_reads_bytes() -> None:
    assert JsonEncoder().decode('{"city": "Iași"}'.encode(), "json") == {"city": "Iași"}


def test_it_writes_text_unescaped_where_json_allows() -> None:
    text = JsonEncoder().encode('é\u2028\x00"\\', "json")

    assert text == '"é\u2028\\u0000\\"\\\\"'


def test_it_reads_escapes() -> None:
    assert JsonEncoder().decode('"\\u00e9\\n\\ud83d\\ude00"', "json") == "é\n\U0001f600"


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_it_refuses_to_read_nan_and_infinity(literal: str) -> None:
    with pytest.raises(NotEncodableValueError, match="not valid JSON"):
        _ = JsonEncoder().decode(f"[{literal}]", "json")


def test_it_refuses_to_read_a_number_too_large_for_a_float() -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().decode('{"a": [1e999]}', "json")

    assert str(raised.value) == "at 'a[0]': Input should be a finite number [type=finite_number]"
    assert raised.value.__context__ is None


@pytest.mark.parametrize(
    ("text", "position"),
    [
        (f'{{"token": "{PLANTED_VALUE}', "line 1 column 28"),
        (f'{{"a": 1}} {PLANTED_VALUE}', "line 1 column 10"),
        (f'{{"{PLANTED_VALUE}":}}', "line 1 column 22"),
        (b"\xff\xfe" + PLANTED_VALUE.encode(), "line 1 column 1"),
        ("", "line 1 column 0"),
    ],
    ids=["truncated", "trailing-garbage", "missing-value", "binary", "empty"],
)
def test_it_refuses_invalid_json_saying_where_but_never_what(
    text: str | bytes, position: str
) -> None:
    with pytest.raises(NotEncodableValueError) as raised:
        _ = JsonEncoder().decode(text, "json")

    message = str(raised.value)
    assert message.startswith("the text is not valid JSON")
    assert message.endswith(f" at {position}")
    assert PLANTED_VALUE not in message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_it_refuses_to_encode_another_format() -> None:
    with pytest.raises(UnsupportedFormatError):
        _ = JsonEncoder().encode({}, "xml")


def test_it_refuses_to_decode_another_format() -> None:
    with pytest.raises(UnsupportedFormatError):
        _ = JsonEncoder().decode("{}", "xml")
