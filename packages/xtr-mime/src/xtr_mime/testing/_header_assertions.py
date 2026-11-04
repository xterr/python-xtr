"""Checks on the headers of a message: present, equal to a value, holding an address."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_mime.exception import LogicError
from xtr_mime.header import MailboxHeader, MailboxListHeader, UnstructuredHeader
from xtr_mime.message import Message

from ._failure import fail

if TYPE_CHECKING:
    from xtr_mime.header import Headers
    from xtr_mime.raw_message import RawMessage

__all__ = [
    "assert_email_address_contains",
    "assert_email_has_header",
    "assert_email_header_not_same",
    "assert_email_header_same",
    "assert_email_not_has_header",
]


def assert_email_has_header(message: RawMessage, header_name: str) -> None:
    """Check ``message`` has a ``header_name`` header.

    Raises:
        AssertionError: When it has none.
        LogicError: When ``message`` is raw bytes, with no headers to read.
    """
    if not _headers_of(message).has(header_name):
        fail(f'the Email has header "{header_name}"')


def assert_email_not_has_header(message: RawMessage, header_name: str) -> None:
    """Check ``message`` has no ``header_name`` header.

    Raises:
        AssertionError: When it has one.
        LogicError: When ``message`` is raw bytes, with no headers to read.
    """
    if _headers_of(message).has(header_name):
        fail(f'the Email does not have header "{header_name}"')


def assert_email_header_same(message: RawMessage, header_name: str, expected_value: str) -> None:
    """Check the ``header_name`` header of ``message`` reads ``expected_value``.

    A text header is compared by its value, any other by its body as written on the wire —
    ``"Fabien <fabien@example.com>"`` for an address.

    Raises:
        AssertionError: When the header reads anything else, or is missing.
        LogicError: When ``message`` is raw bytes, with no headers to read.
    """
    value = _header_value(_headers_of(message), header_name)
    if value != expected_value:
        fail(
            f'the Email has header "{header_name}" with value "{expected_value}" (value is {value})'
        )


def assert_email_header_not_same(
    message: RawMessage, header_name: str, expected_value: str
) -> None:
    """Check the ``header_name`` header of ``message`` is missing or reads another value.

    Raises:
        AssertionError: When the header reads ``expected_value``.
        LogicError: When ``message`` is raw bytes, with no headers to read.
    """
    if _header_value(_headers_of(message), header_name) == expected_value:
        fail(f'the Email does not have header "{header_name}" with value "{expected_value}"')


def assert_email_address_contains(
    message: RawMessage, header_name: str, expected_value: str
) -> None:
    """Check the ``header_name`` address header of ``message`` holds ``expected_value``.

    ``expected_value`` is the bare address, ``fabien@example.com``, whatever name it is
    written with.

    Raises:
        AssertionError: When no address of the header is ``expected_value``.
        LogicError: When ``message`` is raw bytes, or the header is missing or holds no address.
    """
    if not isinstance(message, Message):
        raise LogicError("Unable to test a message address on a RawMessage instance.")
    header = message.get_headers().get(header_name)
    if isinstance(header, MailboxHeader):
        addresses = [header.get_address()]
    elif isinstance(header, MailboxListHeader):
        addresses = header.get_addresses()
    else:
        raise LogicError("Unable to test a message address on a non-address header.")
    if all(address.get_address() != expected_value for address in addresses):
        fail(
            f'the Email contains address "{header_name}" with value "{expected_value}"'
            f" (value is {header.get_body_as_string()})"
        )


def _headers_of(message: RawMessage) -> Headers:
    if not isinstance(message, Message):
        raise LogicError("Unable to test a message header on a RawMessage instance.")
    return message.get_headers()


def _header_value(headers: Headers, header_name: str) -> str | None:
    header = headers.get(header_name)
    if header is None:
        return None
    return (
        header.get_value()
        if isinstance(header, UnstructuredHeader)
        else header.get_body_as_string()
    )
