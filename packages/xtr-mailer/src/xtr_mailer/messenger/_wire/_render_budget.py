"""What sending a queued email costs, bounded once it is read and before a worker renders it.

Rendering folds every header, and some text costs far more to fold than other: text beyond
ASCII is written as encoded words, a few microseconds an octet, and beside an address or in a
parameter — a file name — tens of microseconds an octet, as each word encoded is measured
again and again to fit its line. The limits each header is read under (``_header_limits``) do
not bound how many such headers an email holds across its parts, so what a whole email holds
is bounded too — by limits a real email stays far under, so that the most costly email read
is sent in well under two seconds:

- header text, 192 KiB across the email and its parts: three parts' worth of the 64 KiB one
  part's headers may hold;
- addresses, 2000 across every header: two lists as long as one may be;
- names beside an address or a group, 16 KiB together: a hundred recipients with names as
  long as one may be (256 characters, ``_addresses``);
- text beyond ASCII, counted in UTF-8 octets: 16 KiB in one value and 32 KiB across the email,
  of which 4 KiB in names and parameters — a hundred recipients named in any script;
- parts, 256: the email's, its attachments' and those of every message attached to it.

Each part is counted with the headers it writes — a file name is written as a parameter — and
a part frozen at signing with the headers it was frozen with: it renders nothing again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, assert_never

from xtr_mime import AbstractMultipartPart, Email, Message, MessagePart, SignedBody

from ._header_limits import carried, held_texts
from ._json import refuse

if TYPE_CHECKING:
    from xtr_mime import AbstractPart, Headers, RawMessage

    from ._header_limits import HeldText

__all__ = [
    "ADDRESS_COUNT",
    "FOREIGN_NAME_LENGTH",
    "FOREIGN_TEXT_LENGTH",
    "FOREIGN_VALUE_LENGTH",
    "HEADER_TEXT_LENGTH",
    "NAME_TEXT_LENGTH",
    "PART_COUNT",
    "check_render_cost",
]

HEADER_TEXT_LENGTH: Final = 192 * 1024
ADDRESS_COUNT: Final = 2000
NAME_TEXT_LENGTH: Final = 16 * 1024
FOREIGN_VALUE_LENGTH: Final = 16 * 1024
FOREIGN_TEXT_LENGTH: Final = 32 * 1024
FOREIGN_NAME_LENGTH: Final = 4 * 1024
PART_COUNT: Final = 256


@dataclass(slots=True)
class _Tally:
    """What the email read so far holds, against each limit."""

    header_text: int = 0
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
    _headers(message.get_headers(), tally)
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
        tally.header_text += carried(header)
        for held in held_texts(header):
            _held(held, tally)
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
    if held.kind in {"name", "parameter"}:
        tally.foreign_names += octets


def _check(tally: _Tally) -> None:
    for spent, limit, what in (
        (tally.header_text, HEADER_TEXT_LENGTH, "characters of header text"),
        (tally.addresses, ADDRESS_COUNT, "addresses"),
        (tally.name_text, NAME_TEXT_LENGTH, "characters of names beside addresses"),
        (tally.foreign_text, FOREIGN_TEXT_LENGTH, "octets of header text beyond ASCII"),
        (tally.foreign_names, FOREIGN_NAME_LENGTH, "octets of names and parameters beyond ASCII"),
    ):
        if spent > limit:
            refuse("message", f"holds more than {limit} {what}")
