"""Queued emails as costly to send as the queue lets one be, each grown by one kind of text.

Each shape builds an email holding ``size`` units of the text that costs the most to fold of
its kind — emoji in values, names beside addresses in any script and file names, quoted
names, addresses, values holding ``=?``, parts, headers holding next to nothing — spread over
as many parts as the limits on one part need. At :data:`LIMITS` of its units it is as large as
the queue reads; :func:`most_costly` holds every kind at its limit at once.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

from xtr_mime import Address, DataPart, Email, Headers, Message, MixedPart, TextPart

from xtr_mailer.messenger._wire import write

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["LIMITS", "SHAPES", "most_costly", "queued"]

# Header text one part carries, under the 64 KiB the queue reads for one.
_PART_TEXT: Final = 60_000
# The headers one part carries, as many as the queue reads for one.
_PART_HEADERS: Final = 512
_EMOJI: Final = "\U0001f600"
_CJK: Final = "\u5f20\u4f1f\u660e"
_QUOTED: Final = 'a, "b" (c) '
# A name beyond ASCII costs by its words: one-letter words cost the most for the text held.
_ONE_LETTER_WORDS: Final = "\u0436 "
_RIGHT_TO_LEFT: Final = "\u200f\u05d0\u05d1\u200e "
_COMBINING: Final = "e\u0301\u0302\u0303\u0304"
# Words of 24 characters, as long as one counted by its octets may be, of emoji joined.
_JOINED_EMOJI: Final = "\U0001f468\u200d" * 12 + " "
_ENCODED: Final = "a=?b "


def queued(message: Message) -> str:
    """Write ``message`` as the queue carries it."""
    return json.dumps(write(message, None))


def _email() -> Email:
    return Email().from_("a@example.com").to("b@example.com").text("t")


def _pieces(text: str, size: int, piece: int) -> list[str]:
    """``size`` characters of ``text`` repeated, cut into pieces of at most ``piece``."""
    whole = (text * (size // len(text) + 1))[:size]
    return [whole[start : start + piece] for start in range(0, size, piece)]


def _spread(email: Email, values: list[str], spent: int = 0) -> Email:
    """Add each value as a text header, on the email then on attachments, a part's worth each.

    ``spent`` is the header text the email holds already.
    """
    headers = email.get_headers()
    for value in values:
        if spent + len(value) > _PART_TEXT:
            attachment = DataPart(b"x", "a.bin")
            _ = email.add_part(attachment)
            headers, spent = attachment.get_headers(), 0
        _ = headers.add_text_header("X-A", value)
        spent += len(value) + 3
    return email


def _emoji_values(size: int) -> Email:
    return _spread(_email(), _pieces(_EMOJI, size, 4096))


def _encoded_values(size: int) -> Email:
    return _spread(_email(), _pieces(_ENCODED, size, 8000))


def _named(text: str, size: int) -> Email:
    names = _pieces(text, size, 256)
    return _email().cc(*[Address(f"c{i}@example.com", name) for i, name in enumerate(names)])


def _emoji_names(size: int) -> Email:
    return _named(_EMOJI, size)


def _cjk_names(size: int) -> Email:
    return _named(_CJK, size)


def _accented_names(size: int) -> Email:
    return _named("J\u00fcrgen \u00e9 ", size)


def _quoted_names(size: int) -> Email:
    return _named(_QUOTED, size)


def _addresses(size: int) -> Email:
    email = _email()
    for start in range(0, size, 1000):
        listed = [f"c{i}@example.com" for i in range(start, min(size, start + 1000))]
        _ = email.get_headers().add_mailbox_list_header(f"X-List-{start}", listed)
    return email


def _emoji_file_names(size: int) -> Email:
    email = _email()
    for name in _pieces(_EMOJI, size, 256):
        _ = email.attach(b"x", name)
    return email


def _encoded_parameters(size: int) -> Email:
    return _add_encoded_parameters(_email(), size)


def _add_encoded_parameters(email: Email, size: int) -> Email:
    for start in range(0, size, 56_000):
        values = _pieces(_ENCODED, min(56_000, size - start), 8000)
        attachment = DataPart(b"x", "a.bin")
        held = {f"p{i}": value for i, value in enumerate(values)}
        _ = attachment.get_headers().add_parameterized_header("X-P", "v", held)
        _ = email.add_part(attachment)
    return email


def _flat_parts(size: int) -> Message:
    parts = [TextPart("t") for _ in range(max(1, size - 1))]
    return Message(_message_headers(), MixedPart(*parts))


def _nested_parts(size: int) -> Message:
    """``size`` characters of header text, 8000 a part, each part nested in the next."""
    part: TextPart | MixedPart = TextPart("t")
    for value in _pieces("ab ", size, 8000):
        part = MixedPart(part)
        _ = part.get_headers().add_text_header("X-A", value)
    return Message(_message_headers(), part)


def _headers_holding(value: str) -> Callable[[int], Email]:
    """Build emails of ``size`` headers holding ``value``, on the email then on attachments.

    Each header has a name of its own: what costs most to a part replacing its headers by name.
    """

    def build(size: int) -> Email:
        email = _email()
        # The email holds From and To already.
        headers, held = email.get_headers(), 2
        for index in range(size):
            if held == _PART_HEADERS:
                attachment = DataPart(b"x", "a.bin")
                _ = email.add_part(attachment)
                headers, held = attachment.get_headers(), 0
            _ = headers.add_text_header(f"x{index}", value)
            held += 1
        return email

    return build


def _message_headers() -> Headers:
    headers = Headers().add_mailbox_list_header("From", ["a@example.com"])
    return headers.add_mailbox_list_header("To", ["b@example.com"])


SHAPES: Final[dict[str, Callable[[int], Message]]] = {
    "emoji values": _emoji_values,
    "values holding =?": _encoded_values,
    "emoji names": _emoji_names,
    "CJK names": _cjk_names,
    "accented names": _accented_names,
    "quoted names": _quoted_names,
    "one-letter words in names": lambda size: _named(_ONE_LETTER_WORDS, size),
    "right-to-left names": lambda size: _named(_RIGHT_TO_LEFT, size),
    "combining names": lambda size: _named(_COMBINING, size),
    "joined emoji names": lambda size: _named(_JOINED_EMOJI, size),
    "addresses": _addresses,
    "emoji file names": _emoji_file_names,
    "parameters holding =?": _encoded_parameters,
    "flat parts": _flat_parts,
    "nested parts": _nested_parts,
    "tiny headers": _headers_holding("a"),
    "headers holding =?": _headers_holding("=?"),
}
"""Each shape, by what it grows."""

LIMITS: Final[dict[str, int]] = {
    "emoji values": 8192,
    "values holding =?": 180_000,
    # A word of a name beyond ASCII counts once for every 24 octets, or longer than 24
    # characters once a character.
    "emoji names": 1024,
    "CJK names": 1024,
    "accented names": 4563,
    "quoted names": 16_384,
    "one-letter words in names": 2048,
    "right-to-left names": 5060,
    "combining names": 1024,
    "joined emoji names": 6320,
    # From and To hold the two others.
    "addresses": 1998,
    # A file name is written three times: Content-Type's name, Content-Disposition's name and
    # filename.
    "emoji file names": 2730,
    "parameters holding =?": 180_000,
    "flat parts": 256,
    "nested parts": 192_000,
    # From, To and the three headers each of three attachments writes hold the rest of 2048.
    "tiny headers": 2037,
    "headers holding =?": 2037,
}
"""The size of each shape at which it is as large as the queue reads."""


def most_costly() -> Email:
    """An email holding every costly kind of text at its limit at once.

    Its names beyond ASCII are the costliest they may be — emoji, words as long as a name — and
    the rest of its text beyond ASCII is file names, which cost more an octet than values do.
    """
    email = _named(_EMOJI, LIMITS["emoji names"])
    for name in _pieces(_EMOJI, _MOST_COSTLY_FILE_NAMES, 256):
        _ = email.attach(b"x", name)
    quoted = _pieces(_QUOTED, LIMITS["quoted names"] - LIMITS["emoji names"], 256)
    _ = email.reply_to(*[Address(f"q{i}@example.com", name) for i, name in enumerate(quoted)])
    for start in range(0, 1900, 950):
        listed = [f"l{i}@example.com" for i in range(start, start + 950)]
        _ = email.get_headers().add_mailbox_list_header(f"X-List-{start}", listed)
    _ = _add_encoded_parameters(email, _MOST_COSTLY_ENCODED)
    while len(email.get_attachments()) < 100:
        _ = email.attach(b"x", "a.bin")
    return email


# What the names leave of the text beyond ASCII, then what all leave of the header text.
_MOST_COSTLY_FILE_NAMES: Final = 2389
_MOST_COSTLY_ENCODED: Final = 128_297
