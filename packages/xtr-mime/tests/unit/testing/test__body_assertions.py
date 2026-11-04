"""Checks on what an email says: its subject, its text and HTML bodies, its attachments."""

from __future__ import annotations

import io
import re
from functools import partial
from typing import TYPE_CHECKING, Final

import pytest
from typing_extensions import override

from xtr_mime import Email, Headers, Message, RawMessage
from xtr_mime.exception import InvalidArgumentError, LogicError
from xtr_mime.testing import (
    assert_email_attachment_count,
    assert_email_html_body_contains,
    assert_email_html_body_not_contains,
    assert_email_subject_contains,
    assert_email_subject_not_contains,
    assert_email_text_body_contains,
    assert_email_text_body_not_contains,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_BODY_CHECKS: Final = {
    "text body": (Email.text, assert_email_text_body_contains),
    "text body not": (Email.text, assert_email_text_body_not_contains),
    "html body": (Email.html, assert_email_html_body_contains),
    "html body not": (Email.html, assert_email_html_body_not_contains),
}


def _failure(message: str) -> pytest.RaisesExc[AssertionError]:
    return pytest.raises(AssertionError, match=f"^{re.escape(message)}$")


def test_a_subject_holding_the_text_passes_the_subject_check() -> None:
    assert_email_subject_contains(Email().subject("Your order shipped"), "order")


def test_a_subject_without_the_text_fails_the_subject_check() -> None:
    with _failure(
        'Failed asserting that The email subject contains subject with value "invoice".'
        ' The subject was: "Your order shipped".'
    ):
        assert_email_subject_contains(Email().subject("Your order shipped"), "invoice")


def test_a_missing_subject_fails_the_subject_check_naming_it_empty() -> None:
    with _failure(
        'Failed asserting that The email subject contains subject with value "order".'
        ' The subject was: "<empty>".'
    ):
        assert_email_subject_contains(Email(), "order")


def test_a_subject_without_the_text_passes_the_subject_not_contains_check() -> None:
    assert_email_subject_not_contains(Email(), "order")


def test_a_subject_holding_the_text_fails_the_subject_not_contains_check() -> None:
    with _failure(
        'Failed asserting that The email subject does not contain subject with value "order".'
        ' The subject was: "Your order shipped".'
    ):
        assert_email_subject_not_contains(Email().subject("Your order shipped"), "order")


@pytest.mark.parametrize(
    "message",
    [RawMessage("raw"), Message()],
    ids=["raw message", "message"],
)
def test_the_subject_checks_refuse_what_is_not_an_email(message: RawMessage) -> None:
    error = r"^Can only test a message subject on an Email instance\.$"
    with pytest.raises(LogicError, match=error):
        assert_email_subject_contains(message, "x")
    with pytest.raises(LogicError, match=error):
        assert_email_subject_not_contains(message, "x")


def test_a_text_body_holding_the_text_passes_the_text_body_check() -> None:
    assert_email_text_body_contains(Email().text("Hello world"), "world")


def test_a_text_body_without_the_text_fails_the_text_body_check() -> None:
    email = Email().html("expectedValue").text("actualValue")

    with _failure('Failed asserting that the Email text body contains "expectedValue".'):
        assert_email_text_body_contains(email, "expectedValue")


def test_a_missing_text_body_fails_the_text_body_check() -> None:
    with _failure('Failed asserting that the Email text body contains "x".'):
        assert_email_text_body_contains(Email(), "x")


def test_a_text_body_holding_the_text_fails_the_text_body_not_contains_check() -> None:
    with _failure('Failed asserting that the Email text body does not contain "world".'):
        assert_email_text_body_not_contains(Email().text("Hello world"), "world")


def test_a_text_body_without_the_text_passes_the_text_body_not_contains_check() -> None:
    assert_email_text_body_not_contains(Email().text("Hello"), "world")


def test_a_text_body_given_as_bytes_is_read_in_its_charset() -> None:
    email = Email().text("café".encode("iso-8859-1"), "iso-8859-1")

    assert_email_text_body_contains(email, "café")


def test_a_text_body_given_as_a_file_is_read_from_its_start_every_time() -> None:
    email = Email().text(io.BytesIO(b"Hello world"))

    assert_email_text_body_contains(email, "Hello")
    assert_email_text_body_contains(email, "world")


class _Stream(io.BytesIO):
    @override
    def seekable(self) -> bool:
        return False


def test_a_text_body_given_as_a_stream_is_read_where_it_stands() -> None:
    stream = _Stream(b"Hello world")
    _ = stream.read(6)

    with _failure('Failed asserting that the Email text body contains "Hello".'):
        assert_email_text_body_contains(Email().text(stream), "Hello")


def test_an_html_body_holding_the_text_passes_the_html_body_check() -> None:
    assert_email_html_body_contains(Email().html("<b>Hello</b>"), "<b>Hello")


def test_an_html_body_without_the_text_fails_the_html_body_check() -> None:
    email = Email().html("actualValue").text("expectedValue")

    with _failure('Failed asserting that the Email HTML body contains "expectedValue".'):
        assert_email_html_body_contains(email, "expectedValue")


def test_an_html_body_holding_the_text_fails_the_html_body_not_contains_check() -> None:
    with _failure('Failed asserting that the Email HTML body does not contain "Hello".'):
        assert_email_html_body_not_contains(Email().html("<b>Hello</b>"), "Hello")


def test_an_html_body_without_the_text_passes_the_html_body_not_contains_check() -> None:
    assert_email_html_body_not_contains(Email(), "Hello")


@pytest.mark.parametrize("charset", ["nope", "utf-8\x00"], ids=["unknown", "null byte"])
@pytest.mark.parametrize(("set_body", "check"), _BODY_CHECKS.values(), ids=_BODY_CHECKS.keys())
def test_a_body_in_a_charset_no_codec_reads_fails_the_check_as_it_fails_rendering(
    set_body: Callable[[Email, bytes, str], Email],
    check: Callable[[RawMessage, str], None],
    charset: str,
) -> None:
    email = set_body(Email(), b"Hello", charset)
    with pytest.raises(InvalidArgumentError) as rendering:
        _ = email.get_body().to_string()

    with pytest.raises(InvalidArgumentError) as checking:
        check(email, "Hello")

    assert str(checking.value) == str(rendering.value)


@pytest.mark.parametrize(
    ("check", "error"),
    [
        (
            partial(assert_email_text_body_contains, expected_text="x"),
            "Unable to test a message text body on a RawMessage or Message instance.",
        ),
        (
            partial(assert_email_text_body_not_contains, expected_text="x"),
            "Unable to test a message text body on a RawMessage or Message instance.",
        ),
        (
            partial(assert_email_html_body_contains, expected_text="x"),
            "Unable to test a message HTML body on a RawMessage or Message instance.",
        ),
        (
            partial(assert_email_html_body_not_contains, expected_text="x"),
            "Unable to test a message HTML body on a RawMessage or Message instance.",
        ),
        (
            partial(assert_email_attachment_count, expected_value=0),
            "Unable to test a message attachment on a RawMessage or Message instance.",
        ),
    ],
    ids=["text body", "text body not", "html body", "html body not", "attachment count"],
)
@pytest.mark.parametrize(
    "message",
    [RawMessage("raw"), Message(Headers())],
    ids=["raw message", "message"],
)
def test_the_body_checks_refuse_what_is_not_an_email(
    check: Callable[[RawMessage], None], error: str, message: RawMessage
) -> None:
    with pytest.raises(LogicError, match=f"^{re.escape(error)}$"):
        check(message)


def test_the_attachment_count_passes_when_it_matches() -> None:
    email = Email().attach("one", "one.txt").attach("two", "two.txt")

    assert_email_attachment_count(email, 2)


def test_another_attachment_count_fails_the_check() -> None:
    email = Email().attach("attachment content", "attachment.txt")

    with _failure('Failed asserting that the Email has sent "2" attachment(s).'):
        assert_email_attachment_count(email, 2)
