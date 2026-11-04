"""A header holding one address, such as Sender."""

from __future__ import annotations

from typing import ClassVar, final

from typing_extensions import override

from xtr_mime._engine import Mailbox
from xtr_mime.address import Address

from .abstract_header import AbstractHeader

__all__ = ["MailboxHeader"]


@final
class MailboxHeader(AbstractHeader):
    """A header whose body is one address, written ``name <address>`` or the address alone."""

    __slots__: ClassVar[tuple[str, ...]] = ("_address",)

    def __init__(self, name: str, address: Address) -> None:
        """Keep ``name`` and ``address``.

        Raises:
            RfcComplianceError: ``name`` is not a header name.
        """
        super().__init__(name)
        self._address = address

    @override
    def set_body(self, body: object) -> None:
        """Replace the address.

        Raises:
            InvalidArgumentError: ``body`` is not an :class:`~xtr_mime.Address`.
        """
        if not isinstance(body, Address):
            self._refuse_body("an xtr_mime.Address", body)
        self.set_address(body)

    @override
    def get_body(self) -> Address:
        """Return the address."""
        return self._address

    def set_address(self, address: Address) -> None:
        """Replace the address."""
        self._address = address

    def get_address(self) -> Address:
        """Return the address."""
        return self._address

    @override
    def _engine_value(self) -> list[Mailbox]:
        return [Mailbox(self._address.get_name(), self._address.get_address())]
