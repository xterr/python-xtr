"""Reading the plain data a queued email travels as: each value checked, nothing of it repeated."""

from __future__ import annotations

import pytest

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.messenger._wire._json import (
    built,
    content,
    decoded,
    encoded,
    fields,
    items,
    number,
    optional_text,
    pairs,
    text,
)

_SECRET = "secret\r\nBcc: victim@example.com"


def _refusal(raised: pytest.ExceptionInfo[InvalidArgumentError]) -> str:
    message = str(raised.value)
    assert "secret" not in message
    assert "victim" not in message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    return message


def test_a_refusal_says_where_and_why() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = text(1, "message.subject")

    assert _refusal(raised) == "The queued email cannot be read: message.subject is not text."


def test_an_object_gives_its_fields() -> None:
    assert fields({"a": 1, "b": None}, "x", ("a",), ("b",)) == {"a": 1, "b": None}


def test_an_optional_field_may_be_left_out() -> None:
    assert fields({"a": 1}, "x", ("a",), ("b",)) == {"a": 1}


@pytest.mark.parametrize("data", [[], "a", None, {"a": 1, _SECRET: 2}, {}, {1: 2}], ids=str)
def test_anything_but_an_object_with_its_fields_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = fields(data, "x", ("a",))

    assert _refusal(raised).startswith("The queued email cannot be read: x ")


def test_text_longer_than_its_limit_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = text("a" * 11, "x", 10)

    assert _refusal(raised) == ("The queued email cannot be read: x is longer than 10 characters.")


def test_text_may_be_null_where_it_is_optional() -> None:
    assert optional_text(None, "x") is None
    assert optional_text("a", "x") == "a"


def test_a_list_gives_its_items() -> None:
    assert items([1, "a"], "x") == [1, "a"]


def test_anything_but_a_list_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="x is not a list"):
        _ = items({}, "x")


def test_parameters_are_names_and_values() -> None:
    assert pairs([["a", "1"], ["b", None]], "x") == [("a", "1"), ("b", None)]


@pytest.mark.parametrize("data", [[["a"]], [["a", "1", "2"]], [[1, "1"]], [["a", 1]], ["a"]])
def test_a_parameter_that_is_no_name_and_value_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError, match=r"x\[0\]"):
        _ = pairs(data, "x")


def test_a_number_outside_its_range_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="x is not a whole number from 1 to 9"):
        _ = number(10, "x", 1, 9)


@pytest.mark.parametrize("data", [True, 1.0, "1"])
def test_anything_but_a_whole_number_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = number(data, "x", 0, 9)


def test_bytes_travel_as_base64() -> None:
    assert decoded(encoded(b"\x00\xff"), "x") == b"\x00\xff"


@pytest.mark.parametrize("data", ["not base64!", "QQ", _SECRET, 3])
def test_anything_but_base64_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = decoded(data, "x")

    assert _refusal(raised) == "The queued email cannot be read: x is not base64."


def test_content_is_text_or_bytes_as_it_was_given() -> None:
    assert content({"text": "é"}, "x") == "é"
    assert content({"bytes": encoded(b"\xff")}, "x") == b"\xff"


@pytest.mark.parametrize("data", [{}, {"text": "a", "bytes": ""}])
def test_content_that_is_neither_text_nor_bytes_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError, match="x is not a body"):
        _ = content(data, "x")


def test_what_its_class_refuses_is_refused_without_its_words() -> None:
    def build() -> object:
        raise ValueError(_SECRET)

    with pytest.raises(InvalidArgumentError) as raised:
        _ = built("x", "a header", build)

    assert _refusal(raised) == "The queued email cannot be read: x is not a header."
