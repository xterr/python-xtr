"""A header holding one bare address in angle brackets, such as Return-Path."""

from __future__ import annotations

from typing import ClassVar, final

from typing_extensions import override

from xtr_mime._engine import Path
from xtr_mime.address import Address

from .abstract_header import AbstractHeader

__all__ = ["PathHeader"]


@final
class PathHeader(AbstractHeader):
    """A header whose body is an address written ``<address>`` (RFC 5322, 3.6.7).

    A path has no display name: the address's name, if it has one, is not written. The domain
    is written in punycode; a non-ASCII local part is written as raw UTF-8, the form an
    SMTPUTF8 session carries, as in an address header.
    """

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
    def _engine_value(self) -> Path:
        return Path(self._address.get_encoded_address())
