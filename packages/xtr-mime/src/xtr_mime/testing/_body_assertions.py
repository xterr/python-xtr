"""Checks on what an email says: its subject, its text and HTML bodies, its attachments."""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

from xtr_mime._error_text import body_charset_error
from xtr_mime.email import Email
from xtr_mime.exception import LogicError

from ._failure import fail

if TYPE_CHECKING:
    from xtr_mime.raw_message import RawMessage

__all__ = [
    "assert_email_attachment_count",
    "assert_email_html_body_contains",
    "assert_email_html_body_not_contains",
    "assert_email_subject_contains",
    "assert_email_subject_not_contains",
    "assert_email_text_body_contains",
    "assert_email_text_body_not_contains",
]

_NOT_AN_EMAIL = "Unable to test a message {} on a RawMessage or Message instance."


def assert_email_subject_contains(message: RawMessage, expected_value: str) -> None:
    """Check the subject of ``message`` contains ``expected_value``; a missing one reads empty.

    Raises:
        AssertionError: When it does not.
        LogicError: When ``message`` is not an :class:`~xtr_mime.Email`.
    """
    subject = _subject_of(message)
    if expected_value not in (subject or ""):
        fail(_subject_failure("contains", expected_value, subject))


def assert_email_subject_not_contains(message: RawMessage, expected_value: str) -> None:
    """Check the subject of ``message`` does not contain ``expected_value``.

    Raises:
        AssertionError: When it does.
        LogicError: When ``message`` is not an :class:`~xtr_mime.Email`.
    """
    subject = _subject_of(message)
    if expected_value in (subject or ""):
        fail(_subject_failure("does not contain", expected_value, subject))


def assert_email_text_body_contains(message: RawMessage, expected_text: str) -> None:
    """Check the text body of ``message`` contains ``expected_text``; a missing one reads empty.

    A body given as bytes is read in its charset, one given as a file from its start.

    Raises:
        AssertionError: When it does not.
        LogicError: When ``message`` is not an :class:`~xtr_mime.Email`.
        InvalidArgumentError: When the body is bytes or a file in a charset Python does not
            know, as rendering the email reports it.
    """
    if expected_text not in _text_body_of(message):
        fail(f'the Email text body contains "{expected_text}"')


def assert_email_text_body_not_contains(message: RawMessage, expected_text: str) -> None:
    """Check the text body of ``message`` does not contain ``expected_text``.

    Raises:
        AssertionError: When it does.
        LogicError: When ``message`` is not an :class:`~xtr_mime.Email`.
        InvalidArgumentError: When the body is bytes or a file in a charset Python does not
            know, as rendering the email reports it.
    """
    if expected_text in _text_body_of(message):
        fail(f'the Email text body does not contain "{expected_text}"')


def assert_email_html_body_contains(message: RawMessage, expected_text: str) -> None:
    """Check the HTML body of ``message`` contains ``expected_text``, markup included.

    Raises:
        AssertionError: When it does not.
        LogicError: When ``message`` is not an :class:`~xtr_mime.Email`.
        InvalidArgumentError: When the body is bytes or a file in a charset Python does not
            know, as rendering the email reports it.
    """
    if expected_text not in _html_body_of(message):
        fail(f'the Email HTML body contains "{expected_text}"')


def assert_email_html_body_not_contains(message: RawMessage, expected_text: str) -> None:
    """Check the HTML body of ``message`` does not contain ``expected_text``.

    Raises:
        AssertionError: When it does.
        LogicError: When ``message`` is not an :class:`~xtr_mime.Email`.
        InvalidArgumentError: When the body is bytes or a file in a charset Python does not
            know, as rendering the email reports it.
    """
    if expected_text in _html_body_of(message):
        fail(f'the Email HTML body does not contain "{expected_text}"')


def assert_email_attachment_count(message: RawMessage, expected_value: int) -> None:
    """Check ``message`` carries ``expected_value`` attachments, inline images included.

    Raises:
        AssertionError: When it carries another number.
        LogicError: When ``message`` is not an :class:`~xtr_mime.Email`.
    """
    if not isinstance(message, Email):
        raise LogicError(_NOT_AN_EMAIL.format("attachment"))
    if len(message.get_attachments()) != expected_value:
        fail(f'the Email has sent "{expected_value}" attachment(s)')


def _subject_of(message: RawMessage) -> str | None:
    if not isinstance(message, Email):
        raise LogicError("Can only test a message subject on an Email instance.")
    return message.get_subject()


def _subject_failure(verb: str, expected_value: str, subject: str | None) -> str:
    was = "<empty>" if subject is None else subject
    return (
        f'The email subject {verb} subject with value "{expected_value}". The subject was: "{was}"'
    )


def _text_body_of(message: RawMessage) -> str:
    if not isinstance(message, Email):
        raise LogicError(_NOT_AN_EMAIL.format("text body"))
    return _read(message.get_text_body(), message.get_text_charset())


def _html_body_of(message: RawMessage) -> str:
    if not isinstance(message, Email):
        raise LogicError(_NOT_AN_EMAIL.format("HTML body"))
    return _read(message.get_html_body(), message.get_html_charset())


def _read(body: str | bytes | BinaryIO | None, charset: str | None) -> str:
    if body is None or isinstance(body, str):
        return body or ""
    if not isinstance(body, bytes):
        if body.seekable():
            _ = body.seek(0)
        body = body.read()
    encoding = charset or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except (LookupError, ValueError) as error:
        # No codec goes by that name, or a null byte in it stops the search for one.
        raise body_charset_error(encoding, error) from error
