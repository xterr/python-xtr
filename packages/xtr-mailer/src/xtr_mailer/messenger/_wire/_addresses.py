"""Addresses, groups and the envelope, as a queued email carries them."""

from __future__ import annotations

from typing import Final

from xtr_mime import Address, Group

from xtr_mailer.envelope import Envelope

from ._header_limits import listed
from ._json import JsonObject, built, fields, holds, items, refuse, text

__all__ = [
    "read_address",
    "read_entry",
    "read_envelope",
    "write_address",
    "write_entry",
    "write_envelope",
]

# RFC 3696: 64 octets of local part, an at sign and 255 of domain; checked before the address
# is, so a validator never reads a longer one.
_ADDRESS_LENGTH: Final = 320
# Longer than any name a client shows beside an address; a name is costly to fold, so the
# bound keeps sending a queued email cheap (``_render_budget``).
_NAME_LENGTH: Final = 256


def write_address(address: Address) -> JsonObject:
    """Write an address and its display name."""
    return {"address": address.get_address(), "name": address.get_name()}


def read_address(data: object, path: str) -> Address:
    """Read an address written by :func:`write_address`.

    Raises:
        InvalidArgumentError: It is not one, or is too long.
    """
    found = fields(data, path, ("address", "name"))
    address = text(found["address"], f"{path}.address", _ADDRESS_LENGTH)
    name = text(found["name"], f"{path}.name", _NAME_LENGTH)
    return built(path, "an address", lambda: Address(address, name))


def write_entry(entry: Address | Group) -> JsonObject:
    """Write an entry of an address list: an address, or a group of them under a name."""
    if isinstance(entry, Address):
        return write_address(entry)
    return {"group": entry.get_name(), "addresses": list(map(write_address, entry.get_addresses()))}


def read_entry(data: object, path: str) -> Address | Group:
    """Read an entry written by :func:`write_entry`.

    Raises:
        InvalidArgumentError: It is neither an address nor a group.
    """
    if holds(data, "group"):
        found = fields(data, path, ("group", "addresses"))
        name = text(found["group"], f"{path}.group", _NAME_LENGTH)
        members = listed(found["addresses"], f"{path}.addresses")
        addresses = [
            read_address(member, f"{path}.addresses[{i}]") for i, member in enumerate(members)
        ]
        return built(path, "a group", lambda: Group(name, addresses))
    return read_address(data, path)


def write_envelope(envelope: Envelope | None) -> JsonObject | None:
    """Write the sender and recipients an envelope gives now; ``None`` stays ``None``.

    An envelope read from the email's headers travels as the addresses it gives when the email
    is queued; the recipients go bare, as an envelope keeps them.
    """
    if envelope is None:
        return None
    return {
        "sender": write_address(envelope.get_sender()),
        "recipients": [
            write_address(Address(recipient.get_address()))
            for recipient in envelope.get_recipients()
        ],
    }


def read_envelope(data: object, path: str) -> Envelope | None:
    """Read an envelope written by :func:`write_envelope`.

    Raises:
        InvalidArgumentError: It is not one.
    """
    if data is None:
        return None
    found = fields(data, path, ("sender", "recipients"))
    sender = read_address(found["sender"], f"{path}.sender")
    listed = items(found["recipients"], f"{path}.recipients")
    recipients = [read_address(item, f"{path}.recipients[{i}]") for i, item in enumerate(listed)]
    if not recipients:
        refuse(path, "is not an envelope: it names no recipient")
    return built(path, "an envelope", lambda: Envelope(sender, recipients))
