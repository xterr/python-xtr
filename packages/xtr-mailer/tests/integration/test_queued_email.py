"""Emails queued by the mailer come off a serializing bus as they went on: class, headers, parts.

Upstream's serialization cases are ported here, through the queue rather than ``serialize``:
``RawMessageTest::testSerialization``, ``EmailTest::testSerialize``, the attachment-body cases
and ``testEmailsWithAttachmentsWhichAreAFileInstanceCanBeUnserialized``, and
``RemoteTemplateEmailTest::testSerialization``. Adapted: an attachment from a path is read when
the email is queued and travels as its content — a path read from the queue would let a forged
message read any file the worker can — so its body *is* in the payload.
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from typing import TYPE_CHECKING, BinaryIO
from zoneinfo import ZoneInfo

import pytest
from xtr_messenger import Envelope as BusEnvelope
from xtr_mime import Address, DataPart, DraftEmail, Email, Headers, Message, RawMessage, TextPart

from tests.support.queue import WIRE, through_the_queue
from xtr_mailer import Envelope, RemoteTemplateEmail
from xtr_mailer.header import MetadataHeader, TagHeader, TrackingHeader
from xtr_mailer.messenger import MessageHandler, SendEmailMessage
from xtr_mailer.transport import NullTransport

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_BOUNDARY = re.compile(rb"(boundary=\"?)[^\";\r\n]+|^--[^\r\n]+", re.MULTILINE)
_MADE_UP = re.compile(rb"(?m)^(Date|Message-ID): .*\r\n")


def _shape(message: RawMessage) -> bytes:
    """The rendered message, boundaries and the made-up Date and Message-ID set aside."""
    return _BOUNDARY.sub(b"-", _MADE_UP.sub(b"", b"".join(message.to_iterable())))


def _email() -> Email:
    return Email().from_("a@example.com").to("b@example.com").subject("Über").text("Hi")


def _chunks() -> Iterator[bytes]:
    yield b"some "
    yield b"string"


@pytest.mark.parametrize(
    "content",
    ["some string", b"some string", io.BytesIO(b"some string"), _chunks()],
    ids=["string", "bytes", "stream", "generator"],
)
async def test_a_raw_message_comes_off_the_queue_as_its_bytes_and_is_read_again(
    content: str | bytes | BinaryIO | Iterable[bytes],
) -> None:
    message = RawMessage(content)
    envelope = Envelope(Address("a@example.com"), [Address("b@example.com")])

    queued = await through_the_queue(message, envelope)

    assert type(queued.message) is RawMessage
    assert queued.message.to_string() == "some string"
    assert message.to_string() == "some string"


@pytest.mark.parametrize("kind", [Email, DraftEmail, RemoteTemplateEmail])
async def test_an_email_comes_off_the_queue_of_its_own_class(kind: type[Email]) -> None:
    email = kind().from_("a@example.com").to("b@example.com").subject("Hi").text("Hi")

    queued = await through_the_queue(email, Envelope.create(email))

    assert type(queued.message) is kind
    assert _shape(queued.message) == _shape(email)


async def test_a_message_comes_off_the_queue_a_message() -> None:
    headers = Headers().add_mailbox_list_header("From", ["a@example.com"])
    message = Message(headers.add_mailbox_list_header("To", ["b@example.com"]), TextPart("Hi"))

    queued = await through_the_queue(message)

    assert type(queued.message) is Message
    assert _shape(queued.message) == _shape(message)


async def test_tag_metadata_and_tracking_headers_come_off_the_queue_of_their_classes() -> None:
    email = _email()
    for header in (TagHeader("welcome"), MetadataHeader("Color", "blue"), TrackingHeader(True)):
        _ = email.get_headers().add(header)

    queued = (await through_the_queue(email)).message
    assert isinstance(queued, Email)

    assert [type(h) for h in queued.get_headers().all() if h.get_name().startswith("X-")] == [
        TagHeader,
        MetadataHeader,
        TrackingHeader,
    ]


@pytest.mark.parametrize("fold", [0, 1])
async def test_a_date_in_an_hour_the_clocks_repeat_comes_off_the_queue_the_same_one(
    fold: int,
) -> None:
    zone = ZoneInfo("Europe/Bucharest")
    email = _email().date(datetime(2026, 10, 25, 3, 30, tzinfo=zone, fold=fold))

    queued = (await through_the_queue(email)).message
    assert isinstance(queued, Email)

    date = queued.get_date()
    assert date is not None
    assert (date, date.tzinfo, date.fold) == (email.get_date(), zone, fold)


@pytest.mark.parametrize("fold", [0, 1])
@pytest.mark.parametrize(
    ("zone", "wall_time"),
    [("Europe/Bucharest", (2026, 3, 29, 3, 30)), ("America/New_York", (2026, 3, 8, 2, 30))],
    ids=["Bucharest", "New York"],
)
async def test_a_date_in_an_hour_the_clocks_skip_is_sent_with_the_date_line_sent_directly(
    zone: str, wall_time: tuple[int, int, int, int, int], fold: int
) -> None:
    email = _email().date(datetime(*wall_time, tzinfo=ZoneInfo(zone), fold=fold))
    date_line = re.compile(rb"(?m)^Date: .*$")

    queued = await through_the_queue(email)
    sent = await MessageHandler(NullTransport())(queued)

    assert sent is not None
    assert date_line.findall(sent.to_string().encode()) == date_line.findall(
        email.to_string().encode()
    )


async def test_a_subject_padded_past_a_line_is_sent_by_the_worker_as_it_is_directly() -> None:
    email = _email().subject(f"{'Invoice':<80}#123")

    queued = await through_the_queue(email)
    sent = await MessageHandler(NullTransport())(queued)

    assert sent is not None
    head = sent.to_string().partition("\r\n\r\n")[0]
    assert all(line.strip(" \t") for line in head.split("\r\n"))
    assert _shape(queued.message) == _shape(email)


async def test_inline_and_path_attachments_travel_as_their_content(tmp_path: Path) -> None:
    logo, report = tmp_path / "logo.png", tmp_path / "report.txt"
    _ = logo.write_bytes(b"\x89PNG-logo")
    _ = report.write_bytes(b"foo_bar_xyz_123")
    email = _email().html("<img src='cid:logo.png'>").embed_from_path(logo).attach_from_path(report)
    expected = _shape(email)

    queued = await through_the_queue(email)
    logo.unlink()
    report.unlink()

    assert isinstance(queued.message, Email)
    assert [a.get_body() for a in queued.message.get_attachments()] == [
        b"\x89PNG-logo",
        b"foo_bar_xyz_123",
    ]
    assert _shape(queued.message) == expected


async def test_the_envelope_comes_off_the_queue_with_its_hidden_recipient() -> None:
    envelope = Envelope(
        Address("bounces@example.com"), [Address("b@example.com"), Address("h@x.y")]
    )

    queued = await through_the_queue(_email(), envelope)

    assert queued.envelope is not None
    assert queued.envelope.get_sender() == Address("bounces@example.com")
    assert queued.envelope.get_recipients() == [Address("b@example.com"), Address("h@x.y")]


async def test_without_an_envelope_the_worker_sends_to_every_recipient_the_headers_give() -> None:
    queued = await through_the_queue(_email().bcc("hidden@example.com"))

    sent = await MessageHandler(NullTransport())(queued)

    assert queued.envelope is None
    assert sent is not None
    assert [a.get_address() for a in sent.get_envelope().get_recipients()] == [
        "b@example.com",
        "hidden@example.com",
    ]


async def test_email_serialize() -> None:
    stream = io.BytesIO(b"Text content")
    email = _email().text(stream).html(stream)
    _ = email.add_part(DataPart(io.BytesIO(b"test file"), "test"))
    expected = _shape(email)

    queued = (await through_the_queue(email)).message

    assert isinstance(queued, Email)
    assert queued.get_headers().to_array() == email.get_headers().to_array()
    assert _shape(queued) == expected


def _payload(message: RawMessage) -> str:
    return WIRE.encode(BusEnvelope(SendEmailMessage(message))).body


def test_an_attachment_body_is_part_of_the_payload() -> None:
    payload = _payload(Email().attach(b"foo_bar_xyz_123"))

    assert base64.b64encode(b"foo_bar_xyz_123").decode() in payload


def test_an_attachment_from_a_path_is_part_of_the_payload_and_its_path_is_not(
    tmp_path: Path,
) -> None:
    path = tmp_path / "foo_attachment.txt"
    _ = path.write_bytes(b"foo_bar_xyz_123")

    payload = _payload(Email().attach_from_path(path))

    assert base64.b64encode(b"foo_bar_xyz_123").decode() in payload
    assert str(tmp_path) not in payload


async def test_an_email_with_an_attachment_from_a_path_comes_off_the_queue(tmp_path: Path) -> None:
    path = tmp_path / "foo_attachment.txt"
    _ = path.write_bytes(b"foo_bar_xyz_123")

    queued = (await through_the_queue(_email().attach_from_path(path))).message

    assert isinstance(queued, Email)
    [attachment] = queued.get_attachments()
    assert attachment.get_body() == b"foo_bar_xyz_123"


async def test_a_remote_template_email_comes_off_the_queue_with_its_template() -> None:
    email = RemoteTemplateEmail().from_("fabien@example.com").to("you@example.com")
    _ = email.template("welcome", {"firstName": "Fabien"})

    queued = (await through_the_queue(email)).message

    assert isinstance(queued, RemoteTemplateEmail)
    template = queued.get_remote_template()
    assert template is not None
    assert template.get_reference() == "welcome"
    assert template.get_variables() == {"firstName": "Fabien"}
    assert queued.get_from()[0].get_address() == "fabien@example.com"
