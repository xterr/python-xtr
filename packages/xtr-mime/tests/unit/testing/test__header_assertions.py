"""Checks on the headers of a message: present, equal to a value, holding an address."""

from __future__ import annotations

import re
from functools import partial
from typing import TYPE_CHECKING

import pytest

from xtr_mime import Email, Headers, Message, RawMessage
from xtr_mime.exception import LogicError
from xtr_mime.testing import (
    assert_email_address_contains,
    assert_email_has_header,
    assert_email_header_not_same,
    assert_email_header_same,
    assert_email_not_has_header,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def _failure(message: str) -> pytest.RaisesExc[AssertionError]:
    return pytest.raises(AssertionError, match=f"^{re.escape(message)}$")


def test_a_present_header_passes_the_has_header_check() -> None:
    assert_email_has_header(Email().subject("Hi"), "subject")


def test_a_missing_header_fails_the_has_header_check() -> None:
    headers = Headers().add_mailbox_header("headerName", "test@example.com")

    with _failure('Failed asserting that the Email has header "not existing header".'):
        assert_email_has_header(Email(headers), "not existing header")


def test_a_missing_header_passes_the_not_has_header_check() -> None:
    assert_email_not_has_header(Email(), "X-Missing")


def test_a_present_header_fails_the_not_has_header_check() -> None:
    with _failure('Failed asserting that the Email does not have header "Subject".'):
        assert_email_not_has_header(Email().subject("Hi"), "Subject")


def test_an_equal_text_header_passes_the_header_same_check() -> None:
    assert_email_header_same(Email().subject("Hello there"), "Subject", "Hello there")


def test_a_structured_header_is_compared_as_its_rendered_body() -> None:
    email = Email().to("Fabien <fabien@example.com>")

    assert_email_header_same(email, "To", "Fabien <fabien@example.com>")


def test_another_value_fails_the_header_same_check() -> None:
    with _failure(
        'Failed asserting that the Email has header "Subject" with value "Bye" (value is Hi).'
    ):
        assert_email_header_same(Email().subject("Hi"), "Subject", "Bye")


def test_a_missing_header_fails_the_header_same_check_without_an_error() -> None:
    with _failure(
        'Failed asserting that the Email has header "foo" with value "bar" (value is None).'
    ):
        assert_email_header_same(Email(), "foo", "bar")


def test_another_value_passes_the_header_not_same_check() -> None:
    assert_email_header_not_same(Email().subject("Hi"), "Subject", "Bye")


def test_a_missing_header_passes_the_header_not_same_check() -> None:
    assert_email_header_not_same(Email(), "foo", "bar")


def test_an_equal_value_fails_the_header_not_same_check() -> None:
    with _failure(
        'Failed asserting that the Email does not have header "Subject" with value "Hi".'
    ):
        assert_email_header_not_same(Email().subject("Hi"), "Subject", "Hi")


def test_an_address_in_a_mailbox_header_passes_the_address_check() -> None:
    email = Email().sender("Fabien <fabien@example.com>")

    assert_email_address_contains(email, "Sender", "fabien@example.com")


def test_an_address_in_a_mailbox_list_header_passes_the_address_check() -> None:
    email = Email().to("a@example.com", "Fabien <fabien@example.com>")

    assert_email_address_contains(email, "To", "fabien@example.com")


def test_another_address_in_a_mailbox_header_fails_the_address_check() -> None:
    mailbox_header = "text@example.com"
    headers = Headers().add_mailbox_header(mailbox_header, "actualValue@example.com")

    with _failure(
        'Failed asserting that the Email contains address "text@example.com" with value'
        ' "expectedValue@example.com" (value is actualValue@example.com).'
    ):
        assert_email_address_contains(Email(headers), mailbox_header, "expectedValue@example.com")


def test_an_address_missing_from_a_mailbox_list_header_fails_the_address_check() -> None:
    email = Email().to("a@example.com", "b@example.com")

    with _failure(
        'Failed asserting that the Email contains address "To" with value "c@example.com"'
        " (value is a@example.com, b@example.com)."
    ):
        assert_email_address_contains(email, "To", "c@example.com")


@pytest.mark.parametrize("name", ["Subject", "X-Missing"])
def test_the_address_check_refuses_a_header_holding_no_address(name: str) -> None:
    with pytest.raises(
        LogicError, match=r"^Unable to test a message address on a non-address header\.$"
    ):
        assert_email_address_contains(Email().subject("Hi"), name, "a@example.com")


def test_the_address_check_refuses_a_raw_message() -> None:
    with pytest.raises(
        LogicError, match=r"^Unable to test a message address on a RawMessage instance\.$"
    ):
        assert_email_address_contains(RawMessage("raw"), "To", "a@example.com")


@pytest.mark.parametrize(
    "check",
    [
        partial(assert_email_has_header, header_name="Subject"),
        partial(assert_email_not_has_header, header_name="Subject"),
        partial(assert_email_header_same, header_name="Subject", expected_value="Hi"),
        partial(assert_email_header_not_same, header_name="Subject", expected_value="Hi"),
    ],
    ids=["has header", "not has header", "header same", "header not same"],
)
def test_the_header_checks_refuse_a_raw_message(check: Callable[[RawMessage], None]) -> None:
    with pytest.raises(
        LogicError, match=r"^Unable to test a message header on a RawMessage instance\.$"
    ):
        check(RawMessage("raw"))


def test_the_header_checks_read_a_message_that_is_not_an_email() -> None:
    message = Message(Headers().add_text_header("X-Tag", "a"))

    assert_email_header_same(message, "X-Tag", "a")
