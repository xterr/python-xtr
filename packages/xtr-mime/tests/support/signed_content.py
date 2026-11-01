"""Messages whose body the engine's reader would not read back to the same bytes.

A signature covers the bytes of a body as they were signed; a signed message must send those
bytes again, unchanged, every time it is rendered. Each message here carries, inside its body,
something a read-and-write-again round trip changes: a header written folded before a word too
long for a line, text that starts with whitespace, a forwarded message whose header block is
not written the way the engine writes one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from xtr_mime import DataPart, Email, MessagePart, RawMessage

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["SIGNED_CONTENTS"]

_LONG_TOKEN = "t" * 80


def _outer() -> Email:
    # A Date and a Message-ID of its own: the message's headers render the same every time.
    outer = (
        Email()
        .date(datetime(2020, 1, 1, 10, tzinfo=UTC))
        .from_("me@example.com")
        .to("you@example.com")
        .subject("Fwd")
        .text("fwd")
    )
    _ = outer.get_headers().add_id_header("Message-ID", "outer@example.com")
    return outer


def _inner() -> Email:
    return Email().from_("a@example.org").to("b@example.com").text("x")


def _forwarding(inner: Email) -> Callable[[], Email]:
    return lambda: _outer().add_part(MessagePart(inner))


def _forwarding_raw(raw: bytes) -> Callable[[], Email]:
    return lambda: _outer().add_part(MessagePart(RawMessage(raw)))


def _with_part_header(value: str) -> Callable[[], Email]:
    def build() -> Email:
        part = DataPart(b"data", "a.txt", "text/plain")
        _ = part.get_headers().add_text_header("X-Part", value)
        return _outer().add_part(part)

    return build


def _with_token_header() -> Email:
    inner = _inner()
    _ = inner.get_headers().add_text_header("X-Token", _LONG_TOKEN)
    return _forwarding(inner)()


SIGNED_CONTENTS: dict[str, Callable[[], Email]] = {
    "an attached email with a long token header": _with_token_header,
    "an attached email whose subject starts with a space": _forwarding(_inner().subject(" Re: hi")),
    "an attached email whose subject starts with a tab": _forwarding(_inner().subject("\tRe: hi")),
    "an attached email with a long non-ascii subject": _forwarding(_inner().subject("Grüße " * 15)),
    "a part header with a long token": _with_part_header(_LONG_TOKEN),
    "a part header with leading spaces": _with_part_header("   v"),
    "a forwarded header without a space": _forwarding_raw(b"Subject:x\r\n\r\nbody\r\n"),
    "a forwarded header with a space before its colon": _forwarding_raw(
        b"Subject : x\r\n\r\nbody\r\n"
    ),
    "a forwarded header with spaces after its colon": _forwarding_raw(b"X-A:   v\r\n\r\nbody\r\n"),
    "a forwarded header with a tab after its colon": _forwarding_raw(b"X-B:\tv\r\n\r\nbody\r\n"),
    "a forwarded message with no header block": _forwarding_raw(b"just a body\r\n"),
    "a forwarded message starting with a blank line": _forwarding_raw(b"\r\nbody\r\n"),
    "a forwarded multipart with spaces after its boundaries": _forwarding_raw(
        b'Content-Type: multipart/mixed; boundary="b"\r\n\r\n'
        b"--b  \r\nContent-Type: text/plain\r\n\r\none\r\n--b--  \r\n"
    ),
    "a forwarded multipart left unclosed": _forwarding_raw(
        b'Content-Type: multipart/mixed; boundary="b"\r\n\r\n'
        b"--b\r\nContent-Type: text/plain\r\n\r\none\r\n"
    ),
    "a forwarded header with a bare carriage return": _forwarding_raw(b"X-C: a\rb\r\n\r\nbody\r\n"),
}
"""Builders of the messages, by what each carries; each builds a new message when called."""
