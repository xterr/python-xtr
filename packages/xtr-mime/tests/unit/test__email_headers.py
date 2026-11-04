"""The address and priority headers an email's builder reads and writes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from xtr_mime import Address
from xtr_mime._email_headers import (
    add_addresses,
    get_address,
    get_addresses,
    priority_value,
    read_priority,
    set_addresses,
)
from xtr_mime.header import Headers


def test_get_address_returns_the_address_of_a_mailbox_header() -> None:
    headers = Headers().add_mailbox_header("Sender", "a@example.com")

    assert get_address(headers, "Sender") == Address("a@example.com")


def test_get_address_returns_none_for_a_header_holding_no_address() -> None:
    headers = Headers().add_text_header("X-Sender", "a@example.com")

    assert get_address(headers, "X-Sender") is None


def test_get_addresses_is_empty_for_a_header_holding_no_address_list() -> None:
    headers = Headers().add_text_header("X-To", "a@example.com")

    assert get_addresses(headers, "X-To") == []


def test_add_addresses_adds_the_header_when_it_is_not_there() -> None:
    headers = Headers()

    add_addresses(headers, "To", ["a@example.com"])

    assert get_addresses(headers, "To") == [Address("a@example.com")]


def test_add_addresses_appends_to_the_header_there() -> None:
    headers = Headers()
    add_addresses(headers, "To", ["a@example.com"])

    add_addresses(headers, "To", ["b@example.com"])

    assert get_addresses(headers, "To") == [Address("a@example.com"), Address("b@example.com")]


def test_set_addresses_replaces_the_addresses_of_the_header_there() -> None:
    headers = Headers()
    add_addresses(headers, "To", ["a@example.com"])

    set_addresses(headers, "To", ["b@example.com"])

    assert get_addresses(headers, "To") == [Address("b@example.com")]


@pytest.mark.parametrize(
    ("priority", "value"),
    [(-1, "1 (Highest)"), (2, "2 (High)"), (3, "3 (Normal)"), (4, "4 (Low)"), (9, "5 (Lowest)")],
)
def test_priority_value_is_brought_between_one_and_five(priority: int, value: str) -> None:
    assert priority_value(priority) == value


@pytest.mark.parametrize(
    ("value", "priority"),
    [("1", 1), ("5 (Lowest)", 5), ("4x", 4), ("15", 5), ("5" * 5000, 5)],
    ids=["digit", "labelled", "followed", "two-digits", "many-digits"],
)
def test_read_priority_reads_the_digits_x_priority_starts_with(value: str, priority: int) -> None:
    headers = Headers().add_text_header("X-Priority", value)

    assert read_priority(headers) == priority


@pytest.mark.parametrize("value", ["", "0", "6", "high", " 1"])
def test_read_priority_is_normal_when_x_priority_starts_with_no_priority(value: str) -> None:
    headers = Headers().add_text_header("X-Priority", value)

    assert read_priority(headers) == 3


def test_read_priority_is_normal_without_x_priority() -> None:
    assert read_priority(Headers()) == 3


def test_read_priority_is_normal_when_x_priority_holds_no_text() -> None:
    headers = Headers().add_date_header("X-Priority", datetime(2020, 1, 1, tzinfo=UTC))

    assert read_priority(headers) == 3
