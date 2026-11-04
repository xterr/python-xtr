"""A whole message attached to another, as message/rfc822.

The messages here are fakes rendering fixed bytes, standing in for the message classes; the
serialization case of upstream has no counterpart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from tests.support.rendered_part import read_part
from xtr_mime.header import Headers, ParameterizedHeader, UnstructuredHeader
from xtr_mime.part import MessagePart

if TYPE_CHECKING:
    from collections.abc import Iterator
    from email.message import EmailMessage

RAW: Final = b"From: fabien@example.com\r\nTo: you@example.com\r\n\r\ncontent\r\n"


@final
class _FakeRawMessage:
    """A message that is only bytes, as a raw message is."""

    def to_string(self) -> str:
        return RAW.decode()

    def to_iterable(self) -> Iterator[bytes]:
        yield from RAW.splitlines(keepends=True)


@final
class _FakeMessage:
    """A message with headers, as a built message is."""

    def __init__(self, subject: str) -> None:
        self._headers = Headers().add_text_header("Subject", subject)

    def get_headers(self) -> Headers:
        return self._headers

    def to_string(self) -> str:
        return RAW.decode()

    def to_iterable(self) -> Iterator[bytes]:
        yield from RAW.splitlines(keepends=True)


def test_the_fakes_render_the_same_bytes_either_way() -> None:
    for message in (_FakeRawMessage(), _FakeMessage("Subject")):
        assert message.to_string().encode() == b"".join(message.to_iterable()) == RAW


def test_constructor() -> None:
    part = MessagePart(_FakeMessage("Subject"))

    assert "content" in part.get_body()
    assert "content" in part.body_to_string()
    assert b"content" in b"".join(part.body_to_iterable())
    assert part.get_media_type() == "message"
    assert part.get_media_subtype() == "rfc822"


def test_headers() -> None:
    part = MessagePart(_FakeMessage("Subject"))

    # Adapted: upstream announces base64 and writes the message unencoded; RFC 2046, 5.2.1
    # allows message/rfc822 only 7bit, 8bit or binary, so the message is written in 8bit.
    assert (
        part.get_prepared_headers().to_array()
        == Headers(
            ParameterizedHeader("Content-Type", "message/rfc822", {"name": "Subject.eml"}),
            UnstructuredHeader("Content-Transfer-Encoding", "8bit"),
            ParameterizedHeader(
                "Content-Disposition",
                "attachment",
                {"name": "Subject.eml", "filename": "Subject.eml"},
            ),
        ).to_array()
    )


def test_a_raw_message_is_named_email_eml() -> None:
    assert MessagePart(_FakeRawMessage()).get_filename() == "email.eml"


def test_it_gives_back_the_message_it_carries() -> None:
    message = _FakeMessage("Subject")

    assert MessagePart(message).get_message() is message


def test_the_message_is_written_as_it_renders() -> None:
    part = MessagePart(_FakeRawMessage())

    assert b"".join(part.body_to_iterable()) == RAW
    attached = cast("EmailMessage", read_part(part).get_content())
    assert attached["To"] == "you@example.com"
