"""A header holding message identifiers, such as Message-ID, References or Content-ID."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from xtr_mime._engine import MessageIds
from xtr_mime.address import Address

from .abstract_header import AbstractHeader

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["IdentificationHeader"]


@final
class IdentificationHeader(AbstractHeader):
    """A header whose body is one or more identifiers, each written ``<id>``.

    An identifier has the shape of an address (RFC 5322, 3.6.4: ``id-left@id-right``) and is
    checked as one, so an international right-hand side is written in punycode, as a domain.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_addresses", "_ids")

    def __init__(self, name: str, ids: str | Iterable[str]) -> None:
        """Keep ``name`` and the identifiers, without their angle brackets.

        Raises:
            RfcComplianceError: ``name`` is not a header name, or an identifier does not have
                the shape of an address.
        """
        super().__init__(name)
        self._ids: list[str] = []
        self._addresses: list[Address] = []
        self.set_id(ids)

    @override
    def set_body(self, body: object) -> None:
        """Replace the identifiers with ``body``, one or a sequence of them.

        Raises:
            InvalidArgumentError: ``body`` is neither a string nor a sequence of strings.
            RfcComplianceError: An identifier does not have the shape of an address.
        """
        if isinstance(body, str):
            self.set_id(body)
            return
        if not isinstance(body, Sequence):
            self._refuse_body("a string or a sequence of strings", body)
        ids = [identifier for identifier in body if isinstance(identifier, str)]
        if len(ids) != len(body):
            self._refuse_body("a string or a sequence of strings", body)
        self.set_ids(ids)

    @override
    def get_body(self) -> list[str]:
        """Return the identifiers."""
        return self.get_ids()

    def set_id(self, ids: str | Iterable[str]) -> None:
        """Replace the identifiers with one, or with several.

        Raises:
            RfcComplianceError: An identifier does not have the shape of an address.
        """
        self.set_ids([ids] if isinstance(ids, str) else ids)

    def get_id(self) -> str | None:
        """Return the first identifier, ``None`` when there is none."""
        return self._ids[0] if self._ids else None

    def set_ids(self, ids: Iterable[str]) -> None:
        """Replace the identifiers.

        Raises:
            RfcComplianceError: An identifier does not have the shape of an address.
        """
        given = list(ids)
        self._addresses = [Address(identifier) for identifier in given]
        self._ids = given

    def get_ids(self) -> list[str]:
        """Return the identifiers, as given."""
        return list(self._ids)

    @override
    def _engine_value(self) -> MessageIds:
        return MessageIds(tuple(address.get_encoded_address() for address in self._addresses))
