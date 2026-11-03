"""How much header text a queued email may carry, and what a header value must not hold.

The engine folds a header at a cost that grows faster than its length: a forged header a
hundred kilobytes long, read from a broker, would hold a worker for seconds once the email is
sent. Header text is bounded as it is read instead, by limits a real email stays far under:

- a value — of a text, date, tag, metadata or tracking header, a parameter, an identifier —
  and a folded field, 8 KiB: RFC 5322 caps a line at 998 characters, and the longest fields
  mail carries, DKIM and ARC signatures, fold over a few such lines;
- an address list, a group and an id list, 1000 entries: more recipients than a provider
  takes on one message, more references than a thread gathers;
- the parameters of a header, 64: a Content-Type holds a handful;
- the headers of one message or part together, 64 KiB of text: eight values as long as one
  may be, many times what a signed and tracked email carries.

What a whole email holds across its headers and parts is bounded once it is read
(``_render_budget``), from the pieces of text :func:`held_texts` tells apart.

A value must not hold what would break its line once written — a line break, a control
character but the tab, a line separator or a lone surrogate — which sending would refuse.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, Literal, NamedTuple

from xtr_mime import (
    Address,
    IdentificationHeader,
    MailboxHeader,
    MailboxListHeader,
    ParameterizedHeader,
    PathHeader,
    UnstructuredHeader,
)

from ._json import items, refuse, text

if TYPE_CHECKING:
    from collections.abc import Iterator

    from xtr_mime import Group, HeaderInterface

__all__ = [
    "BLOCK_LENGTH",
    "LIST_LENGTH",
    "PARAMETER_COUNT",
    "VALUE_LENGTH",
    "HeldText",
    "carried",
    "header_value",
    "held_texts",
    "listed",
    "parameters",
]

VALUE_LENGTH: Final = 8 * 1024
LIST_LENGTH: Final = 1000
PARAMETER_COUNT: Final = 64
BLOCK_LENGTH: Final = 64 * 1024

# What the engine refuses to write in a header: every C0 control but the tab, DEL, the C1
# controls, the line and paragraph separators and a lone surrogate.
_FORBIDDEN: Final = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff]")
_PARAMETER_NAME_LENGTH: Final = 64


def header_value(data: object, path: str, limit: int = VALUE_LENGTH) -> str:
    """Give ``data`` as a header value of at most ``limit`` characters.

    Raises:
        InvalidArgumentError: It is not text, is longer, or holds what would break its line.
    """
    value = text(data, path, limit)
    if _FORBIDDEN.search(value):
        refuse(path, "holds a line break, a control character or a lone surrogate")
    return value


def listed(data: object, path: str) -> list[object]:
    """Give the entries of an address list, a group or an id list.

    Raises:
        InvalidArgumentError: ``data`` is not a list, or holds more than 1000 entries.
    """
    return _bounded(items(data, path), path, LIST_LENGTH, "entries")


def parameters(data: object, path: str) -> list[tuple[str, str | None]]:
    """Give the name and value of each parameter in a list of them; a value may be null.

    Raises:
        InvalidArgumentError: ``data`` is no list of names and values, or holds more than 64.
    """
    found: list[tuple[str, str | None]] = []
    for index, pair in enumerate(_bounded(items(data, path), path, PARAMETER_COUNT, "parameters")):
        where = f"{path}[{index}]"
        listed_pair = items(pair, where)
        if len(listed_pair) != 2:  # noqa: PLR2004 -- a name and its value.
            refuse(where, "is not a parameter: a name and its value")
        name = text(listed_pair[0], f"{where}[0]", _PARAMETER_NAME_LENGTH)
        value = listed_pair[1]
        found.append((name, None if value is None else header_value(value, f"{where}[1]")))
    return found


def carried(header: HeaderInterface) -> int:
    """Give the characters of text ``header`` carries: its name and what it holds."""
    return len(header.get_name()) + sum(len(held.text) for held in held_texts(header))


class HeldText(NamedTuple):
    """A piece of text a header holds, and what it is.

    An address; the name shown beside one, or a group's; a parameter's value — a file name
    among them; or any other value: a text, an identifier, a parameter's name.
    """

    text: str
    kind: Literal["value", "address", "name", "parameter"]


def held_texts(header: HeaderInterface) -> Iterator[HeldText]:
    """Give each piece of text ``header`` holds: values, parameters, addresses and their names."""
    # A parameterized header is a text header too: it is matched first.
    match header:
        case ParameterizedHeader():
            yield HeldText(header.get_value(), "value")
            for key, value in header.get_parameters().items():
                yield HeldText(key, "value")
                yield HeldText(value or "", "parameter")
        case UnstructuredHeader():
            yield HeldText(header.get_value(), "value")
        case MailboxHeader() | PathHeader():
            yield from _address(header.get_address())
        case MailboxListHeader():
            for entry in header.get_address_list():
                yield from _entry(entry)
        case IdentificationHeader():
            for identifier in header.get_ids():
                yield HeldText(identifier, "value")
        case _:
            # A date: the engine writes it in a fixed form.
            return


def _bounded(found: list[object], path: str, limit: int, what: str) -> list[object]:
    if len(found) > limit:
        refuse(path, f"holds more than {limit} {what}")
    return found


def _entry(entry: Address | Group) -> Iterator[HeldText]:
    if isinstance(entry, Address):
        yield from _address(entry)
        return
    yield HeldText(entry.get_name(), "name")
    for address in entry.get_addresses():
        yield from _address(address)


def _address(address: Address) -> Iterator[HeldText]:
    yield HeldText(address.get_address(), "address")
    yield HeldText(address.get_name(), "name")
