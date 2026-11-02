"""Messages whose body the engine must write as it was given, and the checks of what is sent.

A text body in ``8bit`` or ``binary`` at the top of a message is written as it is inside a
multipart. An attached message is carried as its own bytes — 8-bit ones included — with its line
ends made CRLF, whatever they were.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email import message_from_bytes, policy
from typing import Final

from xtr_mime import Email, Headers, Message, MessagePart, RawMessage, TextPart

__all__ = ["WRITTEN_CONTENTS", "WrittenContent", "assert_written"]

_DATE: Final = datetime(2020, 1, 1, 10, tzinfo=UTC)
_TEXT: Final = "Grüße\nzwei"
# A binary body is its bytes; text in any other encoding gets a final line break.
_BINARY_BYTES: Final = "Grüße\r\nzwei".encode()
_TEXT_BYTES: Final = "Grüße\r\nzwei\r\n".encode()
_ATTACHED: Final = ["multipart/mixed", "text/plain", "message/rfc822", "text/plain"]
_MAX_LINE_LENGTH: Final = 998


@dataclass(frozen=True, slots=True)
class WrittenContent:
    """A message to build, and what its rendering must carry.

    ``body`` is the bytes written after the headers of the part that holds them: the text, or
    the whole attached message. ``structure`` is the content types a reader walks through, and
    ``payload`` the bytes of the last of them.
    """

    build: Callable[[], Message]
    body: Callable[[], bytes]
    structure: list[str]
    payload: bytes


def _headers(message_id: str) -> Headers:
    headers = (
        Headers()
        .add_date_header("Date", _DATE)
        .add_mailbox_list_header("From", ["me@example.com"])
        .add_mailbox_list_header("To", ["you@example.com"])
        .add_text_header("Subject", "Grüße")
    )
    return headers.add_id_header("Message-ID", message_id)


def _top_level(encoding: str) -> Callable[[], Message]:
    return lambda: Message(_headers("top@example.com"), TextPart(_TEXT, encoding=encoding))


def _attached(message: Callable[[], RawMessage]) -> Callable[[], Message]:
    def build() -> Message:
        outer = Email().date(_DATE).from_("me@example.com").to("you@example.com").text("fwd")
        _ = outer.get_headers().add_id_header("Message-ID", "outer@example.com")
        return outer.add_part(MessagePart(message()))

    return build


def _eight_bit_email() -> Email:
    inner = Email(_headers("inner@example.com"))
    return inner.set_body(TextPart(_TEXT, encoding="8bit"))


def _raw(content: bytes, written: bytes, payload: bytes) -> WrittenContent:
    return WrittenContent(
        _attached(lambda: RawMessage(content)), lambda: written, _ATTACHED, payload
    )


WRITTEN_CONTENTS: dict[str, WrittenContent] = {
    "a top-level 8bit text body": WrittenContent(
        _top_level("8bit"), lambda: _TEXT_BYTES, ["text/plain"], _TEXT_BYTES
    ),
    "a top-level binary text body": WrittenContent(
        _top_level("binary"), lambda: _BINARY_BYTES, ["text/plain"], _BINARY_BYTES
    ),
    "an attached email with an 8bit text body": WrittenContent(
        _attached(_eight_bit_email),
        lambda: b"".join(_eight_bit_email().to_iterable()),
        _ATTACHED,
        _TEXT_BYTES,
    ),
    "an attached raw message with 8-bit bytes": _raw(
        b"Subject: x\r\n\r\nGr\xc3\xbc\xc3\x9fe\r\n",
        b"Subject: x\r\n\r\nGr\xc3\xbc\xc3\x9fe\r\n",
        b"Gr\xc3\xbc\xc3\x9fe\r\n",
    ),
    "an attached raw message with LF line ends": _raw(
        b"Subject: x\n\nline one\nline two\n",
        b"Subject: x\r\n\r\nline one\r\nline two\r\n",
        b"line one\r\nline two\r\n",
    ),
    "an attached raw message with CR line ends": _raw(
        b"Subject: x\r\rline one\rline two\r",
        b"Subject: x\r\n\r\nline one\r\nline two\r\n",
        b"line one\r\nline two\r\n",
    ),
}
"""The messages, by what each carries; each builds a new message when called."""


def assert_written(content: WrittenContent, sent: bytes) -> None:
    """Check ``sent`` carries ``content`` as written, and only CRLF line ends of legal length."""
    assert b"\r\n\r\n" + content.body() in sent
    lines = sent.split(b"\r\n")
    assert not [line for line in lines if b"\r" in line or b"\n" in line]
    assert all(len(line) <= _MAX_LINE_LENGTH for line in lines)
    parts = list(message_from_bytes(sent, policy=policy.default).walk())
    assert [part.get_content_type() for part in parts] == content.structure
    assert parts[-1].get_payload(decode=True) == content.payload
