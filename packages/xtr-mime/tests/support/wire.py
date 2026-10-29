"""Read a rendered header field back the way a mail client does.

Header bytes are the engine's own — its choice of encoded words, its folding points — so a
test compares what a reader gets back, and checks the folding rules, never the bytes.
"""

from __future__ import annotations

import re
from email import policy
from email.header import decode_header, make_header
from email.headerregistry import (
    AddressHeader,
    ContentDispositionHeader,
    HeaderRegistry,
    UnstructuredHeader,
)
from email.parser import HeaderParser
from typing import Final, cast

__all__ = [
    "assert_folded",
    "decode",
    "decode_addresses",
    "decode_parameters",
    "decode_words",
    "encoded_words",
]

_ADDRESSES: Final = HeaderRegistry(default_class=AddressHeader, use_default_map=False)
_PARAMETERS: Final = HeaderRegistry(
    default_class=cast("type[UnstructuredHeader]", ContentDispositionHeader),
    use_default_map=False,
)
_ENCODED_WORD: Final = re.compile(r"=\?[^?]+\?[qQbB]\?[^?]*\?=")


def _split(field: str) -> tuple[str, str]:
    name, _, body = field.partition(":")
    return name, body.replace("\r\n", "").strip()


def decode(field: str) -> str:
    """Return the value of ``field`` (``Name: body``), unfolded and decoded."""
    name = field.split(":", 1)[0]
    parsed = HeaderParser(policy=policy.default).parsestr(field + "\r\n\r\n")
    return str(cast("object", parsed[name]))


def decode_addresses(field: str) -> list[tuple[str, str]]:
    """Return every ``(display name, address)`` of an address field, group members included.

    The parser reads a name as a phrase: it collapses runs of spaces and may split a word
    that spans two encoded words. Use :func:`decode_words` where that matters.
    """
    name, body = _split(field)
    header = cast("AddressHeader", cast("object", _ADDRESSES(name, body)))
    return [(address.display_name, address.addr_spec) for address in header.addresses]


def decode_words(field: str) -> str:
    """Return the body of ``field`` with its encoded words decoded as RFC 2047 says, nothing more.

    Adjacent encoded words join, the whitespace inside them stays, and the rest of the text is
    left as written: what a reader shows of a display name.
    """
    _, body = _split(field)
    return str(make_header(decode_header(body))).strip()


def decode_parameters(field: str) -> dict[str, str]:
    """Return the parameters of a ``value; name=value`` field, RFC 2231 encoding undone."""
    name, body = _split(field)
    header = cast("ContentDispositionHeader", cast("object", _PARAMETERS(name, body)))
    return dict(header.params)


def encoded_words(field: str) -> list[str]:
    """Return the RFC 2047 encoded words of ``field``."""
    return _ENCODED_WORD.findall(field)


def assert_folded(field: str, max_length: int = 76) -> None:
    """Check the folding rules: no line over ``max_length``, every continuation starts with WSP."""
    lines = field.split("\r\n")
    assert all(len(line) <= max_length for line in lines), lines
    assert all(line.startswith((" ", "\t")) for line in lines[1:]), lines
