"""A header holding message identifiers, such as Message-ID, References or Content-ID."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from xtr_mime._engine import MessageIds, check_message_id, encode_idn_address
from xtr_mime.exception import RfcComplianceError

from .abstract_header import AbstractHeader

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["IdentificationHeader"]


@final
class IdentificationHeader(AbstractHeader):
    """A header whose body is one or more identifiers, each written ``<id>``.

    An identifier is an RFC 5322 msg-id, ``id-left@id-right``, not a mail address: its right
    side may hold atoms no domain does. A right side outside ASCII is written in punycode.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_encoded_ids", "_ids")

    def __init__(self, name: str, ids: str | Iterable[str]) -> None:
        """Keep ``name`` and the identifiers, without their angle brackets.

        Raises:
            RfcComplianceError: ``name`` is not a header name, or an identifier is not a
                msg-id.
        """
        super().__init__(name)
        self._ids: list[str] = []
        self._encoded_ids: list[str] = []
        self.set_id(ids)

    @override
    def set_body(self, body: object) -> None:
        """Replace the identifiers with ``body``, one or a sequence of them.

        Raises:
            InvalidArgumentError: ``body`` is neither a string nor a sequence of strings.
            RfcComplianceError: An identifier is not a msg-id.
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
            RfcComplianceError: An identifier is not a msg-id.
        """
        self.set_ids([ids] if isinstance(ids, str) else ids)

    def get_id(self) -> str | None:
        """Return the first identifier, ``None`` when there is none."""
        return self._ids[0] if self._ids else None

    def set_ids(self, ids: Iterable[str]) -> None:
        """Replace the identifiers.

        Raises:
            RfcComplianceError: An identifier is not a msg-id.
        """
        given = list(ids)
        self._encoded_ids = [_encode(self.get_name(), identifier) for identifier in given]
        self._ids = given

    def get_ids(self) -> list[str]:
        """Return the identifiers, as given."""
        return list(self._ids)

    @override
    def _engine_value(self) -> MessageIds:
        return MessageIds(tuple(self._encoded_ids))


def _encode(name: str, identifier: str) -> str:
    try:
        encoded = encode_idn_address(identifier)
        check_message_id(encoded)
    except RfcComplianceError as error:
        # The identifier is not shown: it may hold a line break or a lone surrogate, which an
        # error must not carry into a log.
        raise RfcComplianceError(
            f"An identifier of the {name} header is not a message identifier: "
            "id-left@id-right (RFC 5322, 3.6.4)."
        ) from error
    return encoded
