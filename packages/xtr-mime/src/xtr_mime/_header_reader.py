"""Read a header the way an RFC 2047 mail client does, to check what the engine wrote.

The engine's own reader is lenient where a mail client is not: it keeps the whitespace between
two encoded words of a name, and it takes ``=?...?=`` for an encoded word wherever it finds
one. A header the engine folds is read back here instead, to the letter of RFC 2047: an
encoded word is one only as a whole word, the whitespace between two of them is not text, and
a character split between two of them is joined before it is decoded. Nothing here imports
the engine, so a quirk of the engine cannot hide from it.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Final, Literal, TypeAlias, final

__all__ = ["ReadGroup", "read_address_list", "read_unstructured"]

ReadGroup: TypeAlias = tuple[str | None, list[str]]
"""One item of an address list: the group's name (``None`` for a lone mailbox) and the display
names of its mailboxes, empty for a bare address."""

_Piece: TypeAlias = tuple[Literal["space", "encoded", "text"], str]

_ENCODED_WORD: Final = re.compile(r"=\?([^?*\s]+)(?:\*[^?\s]*)?\?([bBqQ])\?([^?\s]*)\?=")
_QUOTED_BYTE: Final = re.compile(rb"=([0-9A-Fa-f]{2})")
_STRAY_EQUALS: Final = re.compile(r"=(?![0-9A-Fa-f]{2})")
_QUOTED_PAIR: Final = re.compile(r"\\(.)", re.DOTALL)
_FOLD: Final = re.compile(r"\r\n(?=[ \t])")
_SPACE: Final = re.compile(r"([ \t]+)")
# What an address list the engine writes is made of; a comment is not among them.
_TOKEN: Final = re.compile(
    r"(?P<space>[ \t]+)"
    r'|(?P<quoted>"(?:[^"\\]|\\.)*")'
    r'|(?P<angle><(?:"(?:[^"\\]|\\.)*"|[^>"])*>)'
    r"|(?P<special>[,:;])"
    r'|(?P<word>(?:[^\s"(),:;<>\[\]]|\[[^\[\]\\]*\])+)',
    re.DOTALL,
)


def read_unstructured(body: str) -> str:
    """Return the text a mail client shows for an unstructured header body, trimmed.

    Raises:
        ValueError: An encoded word does not decode.
    """
    pieces: list[_Piece] = []
    for part in _SPACE.split(_FOLD.sub("", body)):
        if _SPACE.fullmatch(part):
            pieces.append(("space", part))
        elif part:
            pieces.append(("encoded" if _ENCODED_WORD.fullmatch(part) else "text", part))
    return _decode(pieces)


def read_address_list(body: str) -> list[ReadGroup]:
    """Return the groups and display names a mail client reads in an address header body.

    Raises:
        ValueError: The body is not an address list as the engine writes one, or an encoded
            word in it does not decode.
    """
    reader = _AddressListReader()
    for kind, text in _tokens(body):
        if not reader.feed(kind, text):
            raise _unreadable(body)
    if not reader.end():
        raise _unreadable(body)
    return reader.read


@final
class _AddressListReader:
    """Follows an address list token by token; a step returns whether the list still reads."""

    __slots__ = ("group", "name", "phrase", "read")

    def __init__(self) -> None:
        self.read: list[ReadGroup] = []
        self.group: ReadGroup | None = None
        self.phrase: list[_Piece] = []
        # The display name of the mailbox being read, once its angle address is.
        self.name: str | None = None

    def feed(self, kind: str, text: str) -> bool:
        if kind == "special" and text == ":":
            return self._open_group()
        if kind == "special":
            return self._end_mailbox(closes_group=text == ";")
        if kind == "angle":
            if self.name is not None:
                return False
            self.name, self.phrase = _decode(self.phrase), []
            return True
        if kind != "space" and self.name is not None:
            return False
        self.phrase.append(_piece(kind, text))
        return True

    def end(self) -> bool:
        return self.group is None and self._end_mailbox(closes_group=False)

    def _open_group(self) -> bool:
        if self.group is not None or self.name is not None:
            return False
        self.group, self.phrase = (_decode(self.phrase), []), []
        return True

    def _end_mailbox(self, *, closes_group: bool) -> bool:
        member = self.name
        if member is None and _has_word(self.phrase):
            member = ""
        if member is not None:
            if self.group is None:
                self.read.append((None, [member]))
            else:
                self.group[1].append(member)
        self.phrase, self.name = [], None
        if closes_group:
            if self.group is None:
                return False
            self.read.append(self.group)
            self.group = None
        return True


def _tokens(body: str) -> list[tuple[str, str]]:
    unfolded = _FOLD.sub("", body)
    tokens: list[tuple[str, str]] = []
    position = 0
    while position < len(unfolded):
        match = _TOKEN.match(unfolded, position)
        if match is None or match.lastgroup is None:
            raise _unreadable(body)
        tokens.append((match.lastgroup, match.group()))
        position = match.end()
    return tokens


def _piece(kind: str, text: str) -> _Piece:
    if kind == "space":
        return ("space", text)
    if kind == "quoted":
        return ("text", _QUOTED_PAIR.sub(r"\1", text[1:-1]))
    return ("encoded" if _ENCODED_WORD.fullmatch(text) else "text", text)


def _has_word(phrase: list[_Piece]) -> bool:
    return any(kind != "space" for kind, _ in phrase)


def _decode(pieces: list[_Piece]) -> str:
    """Join ``pieces`` as RFC 2047 reads them: whitespace between encoded words is dropped.

    So is the whitespace around the text, but not a space an encoded word holds: that is
    text, and a reader shows it.
    """
    text: list[str] = []
    run: list[str] = []
    space = ""
    for kind, value in pieces:
        if kind == "space":
            space += value
            continue
        if kind == "encoded" and run:
            run.append(value)
        else:
            text.append(_decode_run(run))
            if text != [""]:
                text.append(space)
            run = [value] if kind == "encoded" else []
            if kind == "text":
                text.append(value)
        space = ""
    text.append(_decode_run(run))
    return "".join(text)


def _decode_run(run: list[str]) -> str:
    """Decode adjacent encoded words, joining the bytes of those in one charset first."""
    text: list[str] = []
    charset = ""
    data = b""
    for word in run:
        word_charset, word_data = _encoded_bytes(word)
        if word_charset != charset:
            text.append(_text_of(word, data, charset))
            data = b""
        charset = word_charset
        data += word_data
    if run:
        text.append(_text_of(run[-1], data, charset))
    return "".join(text)


def _encoded_bytes(word: str) -> tuple[str, bytes]:
    match = _ENCODED_WORD.fullmatch(word)
    if match is None:  # pragma: no cover -- only encoded words are passed in
        raise _undecodable(word)
    charset, encoding, encoded = match.groups()
    try:
        if encoding in "bB":
            return charset.lower(), base64.b64decode(encoded, validate=True)
        if _STRAY_EQUALS.search(encoded):
            raise _undecodable(word)
        raw = encoded.replace("_", " ").encode("ascii")
        return charset.lower(), _QUOTED_BYTE.sub(lambda byte: bytes.fromhex(byte[1].decode()), raw)
    except (binascii.Error, UnicodeError) as error:
        raise _undecodable(word) from error


def _text_of(word: str, data: bytes, charset: str) -> str:
    if not data:
        return ""
    # Only a text encoding decodes here: a codec turning bytes into other bytes — zlib, bz2,
    # base64 — is refused as unknown, and never runs on what a header holds.
    try:
        return data.decode(charset)
    except (LookupError, UnicodeError) as error:
        raise _undecodable(word) from error


def _undecodable(word: str) -> ValueError:
    return ValueError(f"The encoded word {word!r} does not decode.")


def _unreadable(body: str) -> ValueError:
    return ValueError(f"{body!r} is not an address list a mail client reads as written.")
