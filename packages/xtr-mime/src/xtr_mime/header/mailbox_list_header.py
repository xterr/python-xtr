"""A header holding a list of addresses and groups, such as From, To or Cc."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from xtr_mime._engine import Mailbox, MailboxGroup, header_body
from xtr_mime.address import Address
from xtr_mime.group import Group

from .abstract_header import AbstractHeader

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["MailboxListHeader"]


@final
class MailboxListHeader(AbstractHeader):
    """A header whose body is an address list: each entry an address or a group of them.

    Groups (RFC 6854 allows them even in From) are kept as given in :meth:`get_address_list`;
    :meth:`get_addresses` — the body — lists every mailbox, group members included, since that
    is who the message goes to.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_entries",)

    def __init__(self, name: str, addresses: Iterable[Address | Group]) -> None:
        """Keep ``name`` and the address list.

        Raises:
            RfcComplianceError: ``name`` is not a header name.
        """
        super().__init__(name)
        self._entries: list[Address | Group] = list(addresses)

    @staticmethod
    def create_address_list(addresses: Iterable[Address | Group | str]) -> list[Address | Group]:
        """Turn every entry that is not already an address or a group into an address.

        Raises:
            InvalidArgumentError: A string has a ``<`` but no ``Name <address>`` can be read.
            RfcComplianceError: A string is not a valid email address.
        """
        return [entry if isinstance(entry, Group) else Address.create(entry) for entry in addresses]

    @override
    def set_body(self, body: object) -> None:
        """Replace the address list.

        Raises:
            InvalidArgumentError: ``body`` is not a sequence of addresses and groups.
        """
        if isinstance(body, str) or not isinstance(body, Sequence):
            self._refuse_body("a sequence of xtr_mime.Address and xtr_mime.Group", body)
        entries = [entry for entry in body if isinstance(entry, Address | Group)]
        if len(entries) != len(body):
            self._refuse_body("a sequence of xtr_mime.Address and xtr_mime.Group", body)
        self.set_addresses(entries)

    @override
    def get_body(self) -> list[Address]:
        """Return every mailbox, group members included."""
        return self.get_addresses()

    def set_addresses(self, addresses: Iterable[Address | Group]) -> None:
        """Replace the address list."""
        self._entries = list(addresses)

    def add_addresses(self, addresses: Iterable[Address | Group]) -> None:
        """Append to the address list, in order."""
        self._entries.extend(addresses)

    def add_address(self, address: Address | Group) -> None:
        """Append one address or group to the address list."""
        self._entries.append(address)

    def get_addresses(self) -> list[Address]:
        """Return every mailbox, group members included, in order."""
        mailboxes: list[Address] = []
        for entry in self._entries:
            mailboxes.extend(entry.get_addresses() if isinstance(entry, Group) else [entry])
        return mailboxes

    def get_address_list(self) -> list[Address | Group]:
        """Return the address list as given: addresses and groups."""
        return list(self._entries)

    def get_address_strings(self) -> list[str]:
        """Return each entry as written in the header, on one line.

        Raises:
            RfcComplianceError: The engine refuses an entry, such as a name holding an
                encoded word.
        """
        return [
            header_body(self.get_name(), [_engine_entry(entry)]).replace("\r\n", "")
            for entry in self._entries
        ]

    @override
    def _engine_value(self) -> list[Mailbox | MailboxGroup]:
        return [_engine_entry(entry) for entry in self._entries]


def _engine_entry(entry: Address | Group) -> Mailbox | MailboxGroup:
    if isinstance(entry, Group):
        members = tuple(Mailbox(a.get_name(), a.get_address()) for a in entry.get_addresses())
        return MailboxGroup(entry.get_name(), members)
    return Mailbox(entry.get_name(), entry.get_address())
