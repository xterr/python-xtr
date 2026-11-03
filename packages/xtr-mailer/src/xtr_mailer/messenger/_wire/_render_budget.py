"""What sending a queued email costs, bounded once it is read and before a worker renders it.

Rendering folds every header, and some text costs far more to fold than other. Measured on
CPython 3.11 and 3.14, text beyond ASCII costs up to 8 microseconds an octet in a value and up
to 12 an octet written in a parameter — a file name is written three times. A name beside an
address costs by its words instead, whatever its script: up to two thirds of a millisecond
for each word of up to 24 octets, however short, and up to half a millisecond a character
for a word longer than 24 characters, as each encoded word is measured again and again to fit
its line. A name all ASCII is written as it is and costs little; every header costs its share
however little it holds. The limits each header is read under
(``_header_limits``) do not bound how many such headers an email holds across its parts, so
what a whole email holds is bounded too, by limits ordinary mail stays under — hundreds of
recipients named in any script, a hundred attachments with accented names:

- header text, 192 KiB across the email and its parts: three parts' worth of the 64 KiB one
  part's headers may hold;
- headers, 2048 across the email and its parts: each costs its share to send however little it
  holds, and four parts' worth of the 512 one part may hold is more than an email of as many
  parts as it may hold writes;
- addresses, 2000 across every header, Bcc included: two lists as long as one may be;
- names beside an address or a group, 16 KiB together: a hundred recipients with names as
  long as one may be (256 characters, ``_addresses``);
- words of names beyond ASCII, 1024 — a word counted once for every 24 octets it holds begun,
  and one longer than 24 characters once a character: five hundred recipients named in two
  words, in any script;
- text beyond ASCII, counted in UTF-8 octets each time it is written: 16 KiB in one value and
  32 KiB across the email — two hundred attachments with names of thirty octets;
- parts, 256: the email's, its attachments' and those of every message attached to it.

A message's Bcc counts toward the addresses alone: sending takes it out unwritten. Each part
is counted with the headers it writes — a file name is written as a parameter — and a part
frozen at signing with the headers it was frozen with: it renders nothing again.

The most costly email these limits let through, every kind of text at its limit at once, was
sent in 1.5 seconds on CPython 3.14 and 1.7 on 3.11, rendering included.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, assert_never

from xtr_mime import AbstractMultipartPart, Email, Message, MessagePart, SignedBody

from ._header_limits import carried, held_texts
from ._json import refuse

if TYPE_CHECKING:
    from xtr_mime import AbstractPart, HeaderInterface, Headers, RawMessage

    from ._header_limits import HeldText

__all__ = [
    "ADDRESS_COUNT",
    "FOREIGN_NAME_WORDS",
    "FOREIGN_TEXT_LENGTH",
    "FOREIGN_VALUE_LENGTH",
    "HEADER_COUNT",
    "HEADER_TEXT_LENGTH",
    "LONG_WORD_LENGTH",
    "NAME_TEXT_LENGTH",
    "PART_COUNT",
    "WORD_OCTETS",
    "check_render_cost",
]

HEADER_TEXT_LENGTH: Final = 192 * 1024
HEADER_COUNT: Final = 2048
ADDRESS_COUNT: Final = 2000
NAME_TEXT_LENGTH: Final = 16 * 1024
FOREIGN_VALUE_LENGTH: Final = 16 * 1024
FOREIGN_TEXT_LENGTH: Final = 32 * 1024
FOREIGN_NAME_WORDS: Final = 1024
WORD_OCTETS: Final = 24
LONG_WORD_LENGTH: Final = 24
PART_COUNT: Final = 256

# A word as the engine folds it: what runs between spaces and tabs, the only folding whitespace.
_WORD: Final = re.compile(r"[^ \t]+")
_FOREIGN_NAMES: Final = (
    f"words of names beyond ASCII, a word counted once for every {WORD_OCTETS} octets it holds "
    f"and, longer than {LONG_WORD_LENGTH} characters, once a character"
)


@dataclass(slots=True)
class _Tally:
    """What the email read so far holds, against each limit."""

    header_text: int = 0
    headers: int = 0
    addresses: int = 0
    name_text: int = 0
    foreign_text: int = 0
    foreign_names: int = 0
    parts: int = 0


def check_render_cost(message: RawMessage) -> None:
    """Refuse an email whose headers and parts would cost more to send than any real one.

    Raises:
        InvalidArgumentError: It holds more than one of the limits above allows.
    """
    _message(message, _Tally())


def _message(message: object, tally: _Tally) -> None:
    # A raw message is sent as its bytes: it folds no header.
    if not isinstance(message, Message):
        return
    for header in message.get_headers().all():
        if header.get_name().lower() == "bcc":
            _bcc(header, tally)
        else:
            _header(header, tally)
    body = Message.get_body(message)
    if body is not None:
        _part(body, tally)
    if isinstance(message, Email):
        for attachment in message.get_attachments():
            _part(attachment, tally)


def _part(part: AbstractPart, tally: _Tally) -> None:
    tally.parts += 1
    if tally.parts > PART_COUNT:
        refuse("message", f"holds more than {PART_COUNT} parts")
    _headers(part.get_prepared_headers(), tally)
    match part:
        case AbstractMultipartPart():
            for child in part.get_parts():
                _part(child, tally)
        case MessagePart():
            _message(part.get_message(), tally)
        case SignedBody():
            # Frozen at signing: its parts are sent as the bytes they were.
            return
        case _:
            return


def _headers(headers: Headers, tally: _Tally) -> None:
    for header in headers.all():
        _header(header, tally)


def _header(header: HeaderInterface, tally: _Tally) -> None:
    tally.header_text += carried(header)
    tally.headers += 1
    for held in held_texts(header):
        _held(held, tally)
    _check(tally)


def _bcc(header: HeaderInterface, tally: _Tally) -> None:
    """Count the addresses of a message's Bcc, and nothing else: sending takes it out unwritten."""
    tally.addresses += sum(held.kind == "address" for held in held_texts(header))
    _check(tally)


def _held(held: HeldText, tally: _Tally) -> None:
    match held.kind:
        case "address":
            tally.addresses += 1
        case "name":
            tally.name_text += len(held.text)
        case "value" | "parameter":
            pass
        case _:
            assert_never(held.kind)
    if held.text.isascii():
        return
    octets = len(held.text.encode("utf-8", "surrogatepass"))
    if octets > FOREIGN_VALUE_LENGTH:
        refuse("message", f"holds a value of more than {FOREIGN_VALUE_LENGTH} octets beyond ASCII")
    tally.foreign_text += octets
    if held.kind == "name":
        tally.foreign_names += sum(_word_cost(word.group()) for word in _WORD.finditer(held.text))


def _word_cost(word: str) -> int:
    if len(word) > LONG_WORD_LENGTH:
        return len(word)
    return -(-len(word.encode("utf-8", "surrogatepass")) // WORD_OCTETS)


def _check(tally: _Tally) -> None:
    for spent, limit, what in (
        (tally.header_text, HEADER_TEXT_LENGTH, "characters of header text"),
        (tally.headers, HEADER_COUNT, "headers"),
        (tally.addresses, ADDRESS_COUNT, "addresses"),
        (tally.name_text, NAME_TEXT_LENGTH, "characters of names beside addresses"),
        (tally.foreign_text, FOREIGN_TEXT_LENGTH, "octets of header text beyond ASCII"),
        (tally.foreign_names, FOREIGN_NAME_WORDS, _FOREIGN_NAMES),
    ):
        if spent > limit:
            refuse("message", f"holds more than {limit} {what}")
