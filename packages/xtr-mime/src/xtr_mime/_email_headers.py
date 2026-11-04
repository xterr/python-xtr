"""Reads and writes the headers an email sets through its builder: addresses and priority."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from .address import Address
from .header import MailboxListHeader

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .header import Headers

__all__ = [
    "add_addresses",
    "get_address",
    "get_addresses",
    "priority_value",
    "read_priority",
    "set_addresses",
]

_PRIORITY_LABELS: Final[Mapping[int, str]] = {
    1: "Highest",
    2: "High",
    3: "Normal",
    4: "Low",
    5: "Lowest",
}
# Two digits make 11 or more, which brought between 1 and 5 is 5: no more need reading.
_PRIORITY: Final = re.compile(r"[1-5]{1,2}")
_NORMAL: Final = 3


def get_address(headers: Headers, name: str) -> Address | None:
    """Return the address of the first header of that name, ``None`` if it holds none."""
    address = headers.get_header_body(name)
    return address if isinstance(address, Address) else None


def get_addresses(headers: Headers, name: str) -> list[Address]:
    """Return every mailbox of the first header of that name, group members included."""
    header = headers.get(name)
    return header.get_addresses() if isinstance(header, MailboxListHeader) else []


def add_addresses(headers: Headers, name: str, addresses: Iterable[Address | str]) -> None:
    """Append ``addresses`` to the header of that name, adding it if it is not there."""
    header = headers.get(name)
    if isinstance(header, MailboxListHeader):
        header.add_addresses(Address.create_array(addresses))
    else:
        set_addresses(headers, name, addresses)


def set_addresses(headers: Headers, name: str, addresses: Iterable[Address | str]) -> None:
    """Replace the addresses of the header of that name, adding it if it is not there."""
    created = Address.create_array(addresses)
    header = headers.get(name)
    if isinstance(header, MailboxListHeader):
        header.set_addresses(created)
    else:
        _ = headers.add_mailbox_list_header(name, created)


def priority_value(priority: int) -> str:
    """Return the X-Priority value of ``priority``, brought between 1 and 5: ``3 (Normal)``."""
    priority = min(max(priority, 1), 5)
    return f"{priority} ({_PRIORITY_LABELS[priority]})"


def read_priority(headers: Headers) -> int:
    """Return the priority X-Priority starts with, normal (3) when it starts with none.

    Digits from 1 to 5 are read as a number brought between 1 and 5, as :func:`priority_value`
    brings one: several of them make the lowest priority.
    """
    value = headers.get_header_body("X-Priority")
    match = _PRIORITY.match(value) if isinstance(value, str) else None
    return _NORMAL if match is None else min(int(match.group()), 5)
