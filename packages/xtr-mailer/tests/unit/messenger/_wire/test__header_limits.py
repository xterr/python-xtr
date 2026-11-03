"""How much header text a queued email may carry, and the characters it must not hold."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from xtr_mime import (
    Address,
    DateHeader,
    FoldedHeader,
    Group,
    IdentificationHeader,
    MailboxHeader,
    MailboxListHeader,
    ParameterizedHeader,
    PathHeader,
    UnstructuredHeader,
)

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.header import MetadataHeader
from xtr_mailer.messenger._wire._header_limits import (
    LIST_LENGTH,
    PARAMETER_COUNT,
    VALUE_LENGTH,
    carried,
    header_value,
    listed,
    parameters,
)


def test_a_value_as_long_as_the_limit_is_read() -> None:
    assert header_value("a" * VALUE_LENGTH, "x") == "a" * VALUE_LENGTH


def test_a_value_longer_than_the_limit_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=r"^The queued email cannot be read: x is long"):
        _ = header_value("a" * (VALUE_LENGTH + 1), "x")


@pytest.mark.parametrize(
    "value",
    ["a\r\nBcc: victim@example.com", "a\nb", "a\rb", "a\x00b", "a\ud800b", "a\x7fb"],
    ids=["crlf", "lf", "cr", "null", "lone surrogate", "delete"],
)
def test_a_value_holding_what_would_break_its_line_is_refused(value: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = header_value(value, "x")

    assert str(raised.value) == (
        "The queued email cannot be read: x holds a line break, a control character or a lone "
        "surrogate."
    )


def test_a_value_may_hold_a_tab() -> None:
    assert header_value("a\tb", "x") == "a\tb"


def test_a_list_as_long_as_the_limit_is_read() -> None:
    assert len(listed([1] * LIST_LENGTH, "x")) == LIST_LENGTH


def test_a_list_longer_than_the_limit_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=f"x holds more than {LIST_LENGTH} entries"):
        _ = listed([1] * (LIST_LENGTH + 1), "x")


def test_parameters_are_names_and_values() -> None:
    assert parameters([["a", "1"], ["b", None]], "x") == [("a", "1"), ("b", None)]


@pytest.mark.parametrize(
    "data",
    [[["a"]], [["a", "1", "2"]], [[1, "1"]], [["a", 1]], ["a"], [["a" * 65, "1"]]],
    ids=["one", "three", "number name", "number value", "no pair", "long name"],
)
def test_a_parameter_that_is_no_name_and_value_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError, match=r"x\[0\]"):
        _ = parameters(data, "x")


def test_a_parameter_value_longer_than_the_limit_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=r"x\[0\]\[1\] is longer"):
        _ = parameters([["a", "v" * (VALUE_LENGTH + 1)]], "x")


def test_a_parameter_value_holding_a_line_break_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=r"x\[0\]\[1\] holds a line break"):
        _ = parameters([["a", "v\r\nBcc: victim@example.com"]], "x")


def test_more_parameters_than_the_limit_are_refused() -> None:
    data = [[f"p{index}", "v"] for index in range(PARAMETER_COUNT + 1)]

    with pytest.raises(InvalidArgumentError, match=f"x holds more than {PARAMETER_COUNT}"):
        _ = parameters(data, "x")


@pytest.mark.parametrize(
    ("header", "length"),
    [
        (UnstructuredHeader("X-A", "value"), 3 + 5),
        (FoldedHeader("X-A: v1;\r\n v2"), 3 + 6),
        (MetadataHeader("Color", "blue"), 16 + 4),
        (ParameterizedHeader("X-P", "v", {"a": "12", "b": None}), 3 + 1 + 3 + 1),
        (MailboxHeader("Sender", Address("s@example.com", "S")), 6 + 13 + 1),
        (PathHeader("Return-Path", Address("r@example.com")), 11 + 13),
        (MailboxListHeader("To", [Group("Team", ["c@example.com"]), Address("d@x.com")]), 26),
        (IdentificationHeader("References", ["a@example.com", "bb@x.com"]), 10 + 13 + 8),
        (DateHeader("Date", datetime(2026, 11, 3, tzinfo=UTC)), 4),
    ],
    ids=["text", "folded", "metadata", "parameters", "mailbox", "path", "list", "ids", "date"],
)
def test_a_header_carries_its_name_and_the_text_it_holds(
    header: UnstructuredHeader, length: int
) -> None:
    assert carried(header) == length
