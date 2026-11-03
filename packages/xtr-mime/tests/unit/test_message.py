"""A message: headers and a body part, with the headers sending adds.

Upstream's serialization case is xtr-mailer's: it carries a queued message as plain data. Its
case for a Date read without a clock component becomes the Date written at
the offset of the clock's zone: the Date always comes from xtr-clock here.
"""

from __future__ import annotations

import copy
import re
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from typing import TYPE_CHECKING, Final, cast
from zoneinfo import ZoneInfo

import pytest
from xtr_clock import MockClock

from xtr_mime import Address, Group, Message
from xtr_mime.exception import LogicError
from xtr_mime.header import (
    DateHeader,
    Headers,
    IdentificationHeader,
    MailboxHeader,
    MailboxListHeader,
    UnstructuredHeader,
)
from xtr_mime.part import TextPart

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

NO_ORIGINATOR: Final = 'An email must have a "From" or a "Sender" header.'
NO_RECIPIENT: Final = 'An email must have a "To", "Cc", or "Bcc" header.'
NO_FROM_ADDRESS: Final = 'A "From" header must have at least one email address.'


def _from(*addresses: Address | Group | str) -> Message:
    message = Message()
    _ = message.get_headers().add_mailbox_list_header("From", addresses)
    return message


def test_construct() -> None:
    message = Message()
    assert message.get_body() is None
    assert message.get_headers().to_array() == []

    headers = Headers().add_date_header("Date", datetime.now(UTC))
    body = TextPart("content")
    message = Message(headers, body)
    assert message.get_body() is body
    assert message.get_headers() is not headers
    assert message.get_headers().to_array() == headers.to_array()

    message = Message()
    _ = message.set_body(body).set_headers(headers)
    assert message.get_body() is body
    assert message.get_headers() is headers


def test_get_prepared_headers_throws_when_no_from() -> None:
    with pytest.raises(LogicError, match=f"^{re.escape(NO_ORIGINATOR)}$"):
        _ = Message().get_prepared_headers()


def test_get_prepared_headers_with_no_from_and_no_sender() -> None:
    message = Message()
    _ = message.get_headers().add_mailbox_list_header("To", ["you@example.com"])

    with pytest.raises(LogicError, match=f"^{re.escape(NO_ORIGINATOR)}$"):
        _ = message.get_prepared_headers()


def test_get_prepared_headers_clone_headers() -> None:
    message = _from("fabien@example.com")

    assert message.get_prepared_headers() is not message.get_headers()


def test_get_prepared_headers_set_required_headers() -> None:
    headers = _from("fabien@example.com").get_prepared_headers()

    assert headers.has("MIME-Version")
    assert headers.has("Message-ID")
    assert headers.has("Date")
    assert not headers.has("Bcc")


def test_get_prepared_headers() -> None:
    headers = _from("fabien@example.com").get_prepared_headers()

    assert len(list(headers.all())) == 4
    expected_from = MailboxListHeader("From", [Address("fabien@example.com")])
    from_header = headers.get("From")
    assert from_header is not None
    assert from_header.to_string() == expected_from.to_string()
    mime_version = headers.get("mime-version")
    assert isinstance(mime_version, UnstructuredHeader)
    assert mime_version.get_value() == "1.0"
    assert headers.has("Message-Id")
    assert headers.has("Date")


def test_get_prepared_headers_keeps_the_date_set() -> None:
    date = datetime(2005, 10, 15, 12, 34, 56, tzinfo=UTC)
    message = _from("fabien@example.com")
    _ = message.get_headers().add_date_header("Date", date)

    header = message.get_prepared_headers().get("Date")

    assert isinstance(header, DateHeader)
    assert header.get_date_time() == date


def test_get_prepared_headers_removes_bcc() -> None:
    message = _from("fabien@example.com")
    _ = message.get_headers().add_mailbox_list_header("Bcc", ["fabien@example.com"])

    assert message.get_prepared_headers().get("Bcc") is None
    assert message.get_headers().has("Bcc")


def test_get_prepared_headers_date_follows_the_clock() -> None:
    clock = MockClock(datetime(2005, 10, 15, 12, 34, 56, tzinfo=UTC))
    message = Message(clock=clock)
    _ = message.get_headers().add_mailbox_list_header("From", ["fabien@example.com"])

    header = message.get_prepared_headers().get("Date")

    assert isinstance(header, DateHeader)
    assert header.get_date_time() == clock.now()


def test_get_prepared_headers_date_is_written_at_the_offset_of_the_clock() -> None:
    paris = ZoneInfo("Europe/Paris")
    clock = MockClock(datetime(2005, 10, 15, 14, 34, 56, 250000, tzinfo=paris))
    message = Message(clock=clock)
    _ = message.get_headers().add_mailbox_list_header("From", ["fabien@example.com"])

    header = message.get_prepared_headers().get("Date")

    assert header is not None
    assert header.get_body_as_string() == "Sat, 15 Oct 2005 14:34:56 +0200"
    assert isinstance(header, DateHeader)
    assert header.get_date_time().timestamp() == 1129379696.25


def test_get_prepared_headers_with_named_from() -> None:
    headers = _from(Address("fabien@example.com", "Fabien")).get_prepared_headers()

    from_header = headers.get("From")
    assert isinstance(from_header, MailboxListHeader)
    assert from_header.get_address_list() == [Address("fabien@example.com", "Fabien")]
    assert headers.has("Message-Id")


def test_get_prepared_headers_has_no_sender_for_one_from() -> None:
    assert _from("fabien@example.com").get_prepared_headers().get("Sender") is None


def test_get_prepared_headers_takes_the_first_from_as_sender() -> None:
    headers = _from("fabien@example.com", "lucas@example.com").get_prepared_headers()

    sender = headers.get("Sender")
    assert isinstance(sender, MailboxHeader)
    assert sender.get_address().get_address() == "fabien@example.com"


def test_get_prepared_headers_keeps_the_sender_set() -> None:
    message = _from("fabien@example.com", "lucas@example.com")
    _ = message.get_headers().add_mailbox_header("Sender", "thomas@example.com")

    sender = message.get_prepared_headers().get("Sender")

    assert isinstance(sender, MailboxHeader)
    assert sender.get_address().get_address() == "thomas@example.com"


def test_get_prepared_headers_takes_from_from_the_sender() -> None:
    message = Message()
    _ = message.get_headers().add_mailbox_header("Sender", "robot@example.com")

    from_header = message.get_prepared_headers().get("From")

    assert isinstance(from_header, MailboxListHeader)
    assert from_header.get_address_list() == [Address("robot@example.com")]


def test_get_prepared_headers_counts_one_mailbox_of_a_group_in_from() -> None:
    message = _from(Group("Friends", ["fabien@example.com"]))

    assert message.get_prepared_headers().get("Sender") is None


def test_get_prepared_headers_counts_the_mailboxes_of_a_group_in_from() -> None:
    message = _from(Group("Friends", ["fabien@example.com", "lucas@example.com"]))

    sender = message.get_prepared_headers().get("Sender")

    assert isinstance(sender, MailboxHeader)
    assert sender.get_address().get_address() == "fabien@example.com"


def test_get_prepared_headers_with_an_empty_group_in_from_and_a_sender() -> None:
    message = _from(Group("Automated System"))
    _ = message.get_headers().add_mailbox_header("Sender", "robot@example.com")

    headers = message.get_prepared_headers()

    from_header = headers.get("From")
    sender = headers.get("Sender")
    message_id = headers.get("Message-ID")
    assert from_header is not None
    assert sender is not None
    assert message_id is not None
    assert from_header.to_string() == "From: Automated System:;"
    assert sender.to_string() == "Sender: robot@example.com"
    assert message_id.to_string().endswith("@example.com>")


def test_generate_message_id_with_a_group_in_from() -> None:
    message = _from(Group("Friends", ["fabien@example.com"]))

    assert message.generate_message_id().endswith("@example.com")


def test_generate_message_id_is_random_hex_at_the_sender_domain() -> None:
    message = _from("fabien@example.com")
    _ = message.get_headers().add_mailbox_header("Sender", "robot@example.org")

    assert re.fullmatch(r"[0-9a-f]{32}@example\.org", message.generate_message_id())
    assert message.generate_message_id() != message.generate_message_id()


def test_generate_message_id_writes_an_international_domain_in_ascii() -> None:
    message = _from("fabien@bücher.example")

    identifier = message.generate_message_id()

    assert identifier.endswith("@xn--bcher-kva.example")
    _ = IdentificationHeader("Message-ID", identifier).to_string()


def test_generate_message_id_throws_when_from_only_has_an_empty_group() -> None:
    message = _from(Group("undisclosed-recipients"))

    with pytest.raises(LogicError, match=f"^{re.escape(NO_FROM_ADDRESS)}$"):
        _ = message.generate_message_id()


def test_generate_message_id_throws_when_has_from_but_no_addresses() -> None:
    message = _from()

    with pytest.raises(LogicError):
        _ = message.generate_message_id()


def test_generate_message_id_throws_when_neither_from_nor_sender_is_present() -> None:
    with pytest.raises(LogicError, match=f"^{re.escape(NO_ORIGINATOR)}$"):
        _ = Message().generate_message_id()


def _header_names(rendered: str) -> list[str]:
    head = rendered.partition("\r\n\r\n")[0]
    return [line.partition(":")[0] for line in head.split("\r\n")]


def test_to_string_without_a_body_renders_an_empty_text() -> None:
    message = _from("fabien@example.com")

    rendered = message.to_string()

    assert _header_names(rendered) == [
        "From",
        "MIME-Version",
        "Date",
        "Message-ID",
        "Content-Type",
        "Content-Transfer-Encoding",
    ]
    assert re.search(r"\r\nMessage-ID: <[0-9a-f]{32}@example\.com>\r\n", rendered)
    parsed = BytesParser(policy=policy.default).parsebytes(rendered.encode())
    assert parsed.get_content_type() == "text/plain"
    assert parsed.get_content_charset() == "utf-8"
    assert parsed["Content-Transfer-Encoding"] == "quoted-printable"
    assert parsed.get_payload(decode=True) in {b"", b"\r\n", b"\n"}


def test_to_string() -> None:
    message = Message(None, TextPart("content"))
    _ = message.get_headers().add_mailbox_list_header("From", ["fabien@example.com"])

    rendered = message.to_string()

    assert _header_names(rendered)[:4] == ["From", "MIME-Version", "Date", "Message-ID"]
    parsed = BytesParser(policy=policy.default).parsebytes(rendered.encode())
    assert parsed["From"] == "fabien@example.com"
    assert parsed["MIME-Version"] == "1.0"
    assert parsed.get_content_type() == "text/plain"
    assert cast("bytes", parsed.get_payload(decode=True)).rstrip(b"\r\n") == b"content"


def test_to_iterable_renders_what_to_string_does() -> None:
    clock = MockClock(datetime(2005, 10, 15, 12, 34, 56, tzinfo=UTC))
    message = Message(None, TextPart("café"), clock=clock)
    _ = message.get_headers().add_mailbox_list_header("From", ["fabien@example.com"])
    _ = message.get_headers().add_id_header("Message-ID", "fixed@example.com")

    assert b"".join(message.to_iterable()) == message.to_string().encode()


def test_a_copy_has_headers_of_its_own() -> None:
    message = _from("fabien@example.com")

    copied = copy.copy(message)
    _ = copied.get_headers().add_text_header("Subject", "Copy")

    assert not message.get_headers().has("Subject")


ENSURE_VALIDITY: Final[list[tuple[str, Mapping[str, Sequence[str]], str | None]]] = [
    ("valid", {"To": ["dummy@example.com"], "From": ["test@example.com"]}, None),
    ("no destination", {"From": ["test@example.com"]}, NO_RECIPIENT),
    ("empty destination", {"To": [], "From": ["test@example.com"]}, NO_RECIPIENT),
    ("no originator", {"To": ["dummy@example.com"]}, NO_ORIGINATOR),
    ("empty originator", {"To": ["dummy@example.com"], "From": []}, NO_ORIGINATOR),
]


@pytest.mark.parametrize(
    ("headers", "error"),
    [(headers, error) for _, headers, error in ENSURE_VALIDITY],
    ids=[case[0] for case in ENSURE_VALIDITY],
)
def test_ensure_validity(headers: Mapping[str, Sequence[str]], error: str | None) -> None:
    message = Message()
    for name, addresses in headers.items():
        _ = message.get_headers().add_mailbox_list_header(name, addresses)

    if error is None:
        message.ensure_validity()
    else:
        with pytest.raises(LogicError, match=f"^{re.escape(error)}$"):
            message.ensure_validity()


def test_ensure_validity_accepts_a_sender_without_from() -> None:
    message = Message()
    _ = message.get_headers().add_mailbox_list_header("Cc", ["dummy@example.com"])
    _ = message.get_headers().add_mailbox_header("Sender", "robot@example.com")

    message.ensure_validity()
