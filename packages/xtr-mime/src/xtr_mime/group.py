"""A named list of addresses."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from ._display_name import clean_display_name
from .address import Address
from .exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["Group"]


@final
class Group:
    """A display name over a list of addresses, written ``name: a, b;`` (RFC 5322, 3.4).

    A group goes wherever a list of addresses does. With no member it says who received the
    message without naming anyone — ``To: undisclosed-recipients:;``. In From (RFC 6854 allows
    it, for limited use) it leaves the message without an author address, which the Message-ID
    and the SMTP envelope need: set a Sender next to it.
    """

    __slots__ = ("_addresses", "_name")

    def __init__(self, name: str, addresses: Iterable[Address | str] = ()) -> None:
        """Keep ``name``, trimmed and without control characters, and create the members.

        Raises:
            InvalidArgumentError: ``name`` is empty once cleaned: a group is written by its name.
            RfcComplianceError: ``name`` holds a lone surrogate — what a byte that did not
                decode leaves in a str — or a member is not a valid email address.
        """
        self._name = clean_display_name(name, "The group name")
        if not self._name:
            raise InvalidArgumentError("A group must have a display name.")
        self._addresses = tuple(Address.create_array(addresses))

    def get_name(self) -> str:
        """Return the display name."""
        return self._name

    def get_addresses(self) -> list[Address]:
        """Return the members, in order; changing the list leaves the group as it is."""
        return list(self._addresses)
