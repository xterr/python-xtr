"""Values and readers the engine's tests share.

The probes every writer is tried with — control characters, separators, a name that is an
encoded word — and the readers a test reads a field back with, as a mail client would.
"""

from __future__ import annotations

from email import message_from_bytes
from email import policy as stdlib_policy
from email.header import decode_header
from email.parser import HeaderParser
from typing import TYPE_CHECKING, cast

from xtr_mime import _engine
from xtr_mime._engine import TextLeaf

if TYPE_CHECKING:
    from xtr_mime._engine import HeaderValue, Parameterized
    from xtr_mime._engine._values import TransferEncoding

__all__ = [
    "CONTROL_CHARACTERS",
    "ENCODED_WORD_NAME",
    "FUZZ_PIECES",
    "INJECTED_FILENAME",
    "LONG_NAME",
    "LONG_SUBJECT",
    "SEPARATORS",
    "decode_field",
    "lines_of",
    "read_parameter",
    "render_with",
    "rfc2047",
    "text_leaf",
]

LONG_SUBJECT = "Žluťoučký kůň úpěl ďábelské ódy, " * 5

LONG_NAME = ("Žluťoučký kůň úpěl ďábelské ódy " * 4).strip()

# A display name that is itself an encoded word: a reader decoding it would see an address.
ENCODED_WORD_NAME = "=?utf-8?b?ZXZpbEBhdHRhY2tlci5jb20gPGV2aWxAYXR0YWNrZXIuY29tPg==?="

# Every C0 control but TAB, and DEL: none may reach a header, whatever the Python patch level.
CONTROL_CHARACTERS = ["\r", "\n", "\r\n", "\x00", "\x0b", "\x0c", "\x1b", "\x1f", "\x7f"]

# Line and paragraph separators, C1 controls (NEL among them) and a lone surrogate: some
# readers end a line at the first ones, and the last is a byte that was never text.
SEPARATORS = ["\u2028", "\u2029", "\x85", "\x80", "\x9f", "\ud800", "\udc80"]

INJECTED_FILENAME = "a.txt\r\nBcc: x@y.z"

FUZZ_PIECES = (
    "a", "Ž", "ø", " ", "  ", "\t", '"', "\\", "<", ">", "@", ",", ";", ":", ".", "(", ")", "[",
    "]", "=?", "?=", "=?utf-8?b?", "=?utf-8?q?", "?q?", "?b?", "_", "=0A", "=0D", "=0B", "=C5",
    "\r\n", "\n", "\x0b", "\x00", "\x7f", "\x85", "\u2028", "\ud800", "x" * 80, "Bcc: ",
    "evil@attacker.com",
)  # fmt: skip


def decode_field(field: str) -> str:
    """Read one rendered header field back the way a mail client would."""
    name = field.split(":", 1)[0]
    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    return cast("str", parsed[name])


def rfc2047(text: str) -> str:
    """Decode ``text`` as RFC 2047 says: whitespace between two encoded words is dropped."""
    parts: list[tuple[bytes | str, str | None]] = decode_header(text.replace("\r\n", ""))
    return "".join(
        part.decode(charset or "ascii") if isinstance(part, bytes) else part
        for part, charset in parts
    )


def lines_of(field: str) -> list[str]:
    return field.split("\r\n")


def text_leaf(  # noqa: PLR0913 -- a test builder: every field a test may vary is a keyword
    content: str = "Hello",
    *,
    subtype: str = "plain",
    charset: str = "utf-8",
    transfer_encoding: TransferEncoding = "quoted-printable",
    parameters: dict[str, str] | None = None,
    disposition: Parameterized | None = None,
) -> TextLeaf:
    return TextLeaf(
        content=content,
        subtype=subtype,
        charset=charset,
        transfer_encoding=transfer_encoding,
        parameters=parameters or {},
        disposition=disposition,
    )


def render_with(name: str, value: HeaderValue) -> bytes:
    return _engine.to_bytes(_engine.build_message([(name, value)], _engine.build_text(text_leaf())))


def read_parameter(field: str, header: str, parameter: str) -> tuple[object, object, str]:
    """What the stdlib reader and ``decode_header`` make of ``parameter`` in ``field``."""
    parsed = message_from_bytes(f"{field}\r\n\r\nx".encode(), policy=stdlib_policy.default)
    return (
        parsed.get_filename() if parameter == "filename" else parsed.get_param(parameter),
        parsed.get_param(parameter, header=header),
        rfc2047(field),
    )
