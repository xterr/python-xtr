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

A value must not hold what would break its line once written — a line break, a control
character but the tab, a line separator or a lone surrogate — which sending would refuse.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

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
    from xtr_mime import Group, HeaderInterface

__all__ = [
    "BLOCK_LENGTH",
    "LIST_LENGTH",
    "PARAMETER_COUNT",
    "VALUE_LENGTH",
    "carried",
    "header_value",
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
    return len(header.get_name()) + _held(header)


def _bounded(found: list[object], path: str, limit: int, what: str) -> list[object]:
    if len(found) > limit:
        refuse(path, f"holds more than {limit} {what}")
    return found


def _held(header: HeaderInterface) -> int:
    # A parameterized header is a text header too: it is matched first.
    match header:
        case ParameterizedHeader():
            held = header.get_parameters().items()
            return len(header.get_value()) + sum(len(k) + len(v or "") for k, v in held)
        case UnstructuredHeader():
            return len(header.get_value())
        case MailboxHeader() | PathHeader():
            return _address(header.get_address())
        case MailboxListHeader():
            return sum(map(_entry, header.get_address_list()))
        case IdentificationHeader():
            return sum(map(len, header.get_ids()))
        case _:
            # A date: the engine writes it in a fixed form.
            return 0


def _entry(entry: Address | Group) -> int:
    if isinstance(entry, Address):
        return _address(entry)
    return len(entry.get_name()) + sum(map(_address, entry.get_addresses()))


def _address(address: Address) -> int:
    return len(address.get_address()) + len(address.get_name())
