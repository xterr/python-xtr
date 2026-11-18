from __future__ import annotations

import io
from typing import TYPE_CHECKING

from xtr_mime import Email, Message, RawMessage
from xtr_mime.part import DataPart, File

from xtr_mailer import Envelope, SentMessage
from xtr_mailer.data_collector._mail_record import MailRecord
from xtr_mailer.data_collector._masking import MASK
from xtr_mailer.data_collector._message_data import message_data
from xtr_mailer.event import MessageEvent
from xtr_mailer.exception import TransportError

if TYPE_CHECKING:
    from pathlib import Path

_SENDER = Envelope.create(Email().from_("shop@example.com").to("customer@example.com"))


def _email() -> Email:
    return Email().from_("shop@example.com").to("customer@example.com").text("Hello")


def _record(message: RawMessage, queued: bool = False) -> MailRecord:
    return MailRecord(MessageEvent(message, _SENDER, "smtp://mail.example.com", queued=queued))


def _sent(record: MailRecord) -> SentMessage:
    sent = SentMessage(record.event.get_message(), record.event.get_envelope())
    record.sent = sent
    return sent


def test_an_email_is_described_by_its_fields() -> None:
    email = (
        Email()
        .from_("Shop <shop@example.com>")
        .to("customer@example.com", "Other <other@example.com>")
        .cc("cc@example.com")
        .bcc("bcc@example.com")
        .reply_to("help@example.com")
        .subject("Your order")
        .text("Thanks")
        .html("<p>Thanks</p>")
    )

    data = message_data(_record(email))

    assert data["transport"] == "smtp://mail.example.com"
    assert data["queued"] is False
    assert data["status"] == "pending"
    assert data["subject"] == "Your order"
    assert data["from"] == ["Shop <shop@example.com>"]
    assert data["to"] == ["customer@example.com", "Other <other@example.com>"]
    assert (data["cc"], data["bcc"], data["reply_to"]) == (
        ["cc@example.com"],
        ["bcc@example.com"],
        ["help@example.com"],
    )
    assert (data["text"], data["html"]) == ("Thanks", "<p>Thanks</p>")
    assert (data["message_id"], data["debug"], data["error"], data["size"]) == (
        None,
        None,
        None,
        None,
    )


def test_the_headers_are_kept_by_name_with_credentials_masked() -> None:
    email = _email().subject("Hi")
    headers = email.get_headers()
    _ = headers.add_text_header("X-Api-Key", "key-123")
    _ = headers.add_text_header("X-Auth-Token", "tok-456")
    _ = headers.add_text_header("X-Tag", "one")
    _ = headers.add_text_header("X-Tag", "two")

    data = message_data(_record(email))

    assert data["headers"] == {
        "From": "shop@example.com",
        "To": "customer@example.com",
        "Subject": "Hi",
        "X-Api-Key": MASK,
        "X-Auth-Token": MASK,
        "X-Tag": "one\ntwo",
    }


def test_a_header_the_engine_refuses_is_shown_as_given() -> None:
    email = _email()
    _ = email.get_headers().add_text_header("X-Bad", "a\x00b")

    headers = message_data(_record(email))["headers"]

    assert isinstance(headers, dict)
    assert headers["X-Bad"] == "a\x00b"


def test_the_text_and_html_bodies_are_cut_to_their_limits() -> None:
    email = _email().text("t" * 10_001).html("h" * 50_001)

    data = message_data(_record(email))

    assert data["text"] == "t" * 10_000
    assert data["html"] == "h" * 50_000


def test_a_bytes_body_is_decoded_in_its_charset() -> None:
    email = _email().text("café".encode("latin-1"), charset="latin-1")

    assert message_data(_record(email))["text"] == "café"


def test_a_bytes_body_in_an_unknown_charset_is_read_as_utf_8() -> None:
    email = _email().text("café".encode(), charset="no-such-charset")

    assert message_data(_record(email))["text"] == "café"


def test_a_file_body_is_not_read() -> None:
    stream = io.BytesIO(b"<p>Hi</p>")
    email = _email().html(stream)

    assert message_data(_record(email))["html"] is None
    assert stream.tell() == 0


def test_each_attachment_is_described_by_name_type_and_size() -> None:
    email = _email().attach(b"%PDF-1.7", "invoice.pdf", "application/pdf").attach("é", "note.txt")

    attachments = message_data(_record(email))["attachments"]

    assert attachments == [
        {"filename": "invoice.pdf", "content_type": "application/pdf", "size": 8},
        {"filename": "note.txt", "content_type": "application/octet-stream", "size": 2},
    ]


def test_an_attachment_that_can_no_longer_be_read_has_no_size(tmp_path: Path) -> None:
    path = tmp_path / "gone.txt"
    _ = path.write_bytes(b"soon gone")
    email = _email().add_part(DataPart(File(path)))
    path.unlink()

    attachments = message_data(_record(email))["attachments"]

    assert attachments == [{"filename": "gone.txt", "content_type": "text/plain", "size": None}]


def test_a_sent_email_has_its_message_id_transcript_and_size() -> None:
    record = _record(_email())
    sent = _sent(record)
    sent.append_debug("250 Ok")

    data = message_data(record)

    assert data["status"] == "sent"
    assert data["message_id"] == sent.get_message_id()
    assert data["debug"] == "250 Ok"
    assert data["size"] == len(sent.to_string().encode())


def test_a_failed_email_has_the_error_and_its_transcript() -> None:
    record = _record(_email())
    error = TransportError("Connection refused.")
    error.append_debug("> EHLO\r\n")
    record.error = error

    data = message_data(record)

    assert data["status"] == "failed"
    assert (data["error"], data["debug"]) == ("Connection refused.", "> EHLO\r\n")


def test_an_error_without_a_message_is_named_by_its_type() -> None:
    record = _record(_email())
    record.error = RuntimeError()

    data = message_data(record)

    assert (data["error"], data["debug"]) == ("RuntimeError", None)


def test_a_queued_email_says_so() -> None:
    data = message_data(_record(_email(), queued=True))

    assert (data["queued"], data["status"]) == (True, "queued")


def test_a_raw_message_keeps_its_size_and_no_fields() -> None:
    content = b"Subject: Hi\r\n\r\nHello"

    data = message_data(_record(RawMessage(content)))

    assert data["size"] == len(content)
    assert (data["subject"], data["to"], data["headers"], data["text"]) == (None, [], {}, None)


def test_a_raw_message_that_can_no_longer_be_read_has_no_size() -> None:
    message = RawMessage(iter([b"Subject: Hi\r\n", b"\r\n"]))
    chunks = message.to_iterable()
    _ = next(chunks)
    chunks.close()

    assert message_data(_record(message))["size"] is None


def test_an_email_replaced_by_a_signed_message_is_described_as_announced() -> None:
    email = _email().subject("Signed")
    record = _record(email)
    record.event.set_message(Message(email.get_headers()))

    assert message_data(record)["subject"] == "Signed"


def test_a_message_that_is_not_an_email_and_was_not_sent_has_no_size() -> None:
    message = Message()
    _ = message.get_headers().add_text_header("Subject", "Hi")

    data = message_data(_record(message))

    assert (data["size"], data["subject"]) == (None, None)
