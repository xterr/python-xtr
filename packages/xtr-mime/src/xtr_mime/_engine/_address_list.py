"""Address headers, written so a reader gets back the names and addresses they were given."""

from __future__ import annotations

import re
from email.headerregistry import Address, Group
from email.utils import quote
from typing import TYPE_CHECKING, Final

from xtr_mime._header_reader import ReadGroup, read_address_list
from xtr_mime.exception import RfcComplianceError

from ._addresses import to_engine_address
from ._grammar import FOLD_WIDTH, body_of
from ._policy import ADDRESS, POLICY, UTF8_POLICY, FoldedHeader, address_groups
from ._unstructured import encoded_words

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from ._values import Mailbox, MailboxGroup

__all__ = ["address_header", "check_reads_back", "write_address_list"]

# Words a name is written as when the engine writes it unquoted: atext, non-ASCII included
# (RFC 6532), one space apart.
_ATOM: Final = r"[^\x00-\x20\x7f()<>\[\]:;@\\,.\"]+"
_PHRASE: Final = re.compile(rf"{_ATOM}(?: {_ATOM})*")


def address_header(name: str, value: Sequence[Mailbox | MailboxGroup]) -> FoldedHeader:
    """Build an address header, folded once: the fold read back is the one kept."""
    items = [to_engine_address(item) for item in value]
    header = ADDRESS(name, items)
    utf8 = any(not address.username.isascii() for address in _addresses_of(items))
    written = header.fold(policy=UTF8_POLICY if utf8 else POLICY)
    folded = (
        written
        if _names_read_back(name, items, written)
        else write_address_list(name, items, utf8=utf8)
    )
    if not _names_read_back(name, items, folded):
        raise RfcComplianceError(
            f"The {name} header would not read back to the names it was given: {folded!r}."
        )
    check_reads_back(name, items, folded)
    return FoldedHeader(name, str(header), folded)


def _names_read_back(name: str, items: Sequence[Address | Group], folded: str) -> bool:
    """Tell whether a mail client reads the groups and names ``items`` hold in ``folded``."""
    given: list[ReadGroup] = [
        (
            (item.display_name or "").strip(" \t"),
            [address.display_name.strip(" \t") for address in item.addresses],
        )
        if isinstance(item, Group)
        else (None, [item.display_name.strip(" \t")])
        for item in items
    ]
    try:
        return read_address_list(body_of(name, folded)) == given
    except ValueError:
        return False


def write_address_list(name: str, items: Sequence[Address | Group], *, utf8: bool) -> str:
    """Write an address header the engine's folding would not write faithfully.

    A name is written as atoms, as a quoted string, or — when not ASCII and the header is not
    raw UTF-8 — as the package's legacy encoded words, which keep every space inside a word.
    The field is folded between words, at 76 columns where a word allows.
    """
    words: list[str] = []
    for position, item in enumerate(items):
        if position:
            words[-1] += ","
        if isinstance(item, Group):
            words += _phrase_words(item.display_name or "", utf8=utf8) or [""]
            words[-1] += ":"
            for index, member in enumerate(item.addresses):
                if index:
                    words[-1] += ","
                words += _mailbox_words(member, utf8=utf8)
            words[-1] += ";"
        else:
            words += _mailbox_words(item, utf8=utf8)
    lines = [f"{name}:"]
    for word in words:
        if len(lines[-1]) + 1 + len(word) > FOLD_WIDTH:
            lines.append(f" {word}")
        else:
            lines[-1] += f" {word}"
    return "\r\n".join(lines) + "\r\n"


def _mailbox_words(address: Address, *, utf8: bool) -> list[str]:
    phrase = _phrase_words(address.display_name, utf8=utf8)
    return [*phrase, f"<{address.addr_spec}>"] if phrase else [address.addr_spec]


def _phrase_words(display_name: str, *, utf8: bool) -> list[str]:
    text = display_name.strip(" \t")
    if not text:
        return []
    if utf8 or text.isascii():
        return text.split(" ") if _PHRASE.fullmatch(text) else [f'"{quote(text)}"']
    return encoded_words(text)


def _addresses_of(items: Sequence[Address | Group]) -> Iterator[Address]:
    for item in items:
        if isinstance(item, Group):
            yield from item.addresses
        else:
            yield item


def check_reads_back(name: str, items: Sequence[Address | Group], folded: str) -> None:
    """Refuse a header that a reader would take for other addresses than the ones given.

    The engine reads the header it writes back into words before folding them, so what it
    folds is its reading of the value, not the value: a name it decoded from an encoded word
    comes out as plain text, where it reads as an address. Names are kept literal before they
    get here; this catches whatever other reading the engine may make of a value.
    """
    given = [
        (True, tuple(a.addr_spec for a in item.addresses))
        if isinstance(item, Group)
        else (False, (item.addr_spec,))
        for item in items
    ]
    if address_groups(name, body_of(name, folded)) != given:
        raise RfcComplianceError(
            f"The {name} header would not read back to the addresses it was given: {folded!r}."
        )
