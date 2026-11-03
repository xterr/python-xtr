"""A header written exactly as it was folded: a field a signature covers byte for byte."""

from __future__ import annotations

from typing import ClassVar, final

from typing_extensions import override

from xtr_mime._engine import check_folded

from .unstructured_header import UnstructuredHeader

__all__ = ["FoldedHeader"]


@final
class FoldedHeader(UnstructuredHeader):
    """A text header kept as the field it was given, folding and all, and written as it is.

    The engine folds every header it writes its own way. A field folded elsewhere — the
    DKIM-Signature a signer wrote, which ``simple`` header canonicalization hashes byte for
    byte — would no longer be the same bytes refolded, so it is written as given. Its value is
    the field unfolded; setting another value drops the folding, and the engine writes that one.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_folded",)

    def __init__(self, field: str) -> None:
        """Keep ``field``, ``Name: value`` folded with CRLF, once checked to be one header.

        Raises:
            RfcComplianceError: The name is not a header name, or a line of the field would
                start a header of its own, holds a control character or is longer than 998
                octets.
        """
        folded = field.removesuffix("\r\n")
        name, _, value = folded.partition(":")
        super().__init__(name, value.replace("\r\n", "").strip(" "))
        check_folded(folded + "\r\n")
        self._folded: str | None = folded

    @override
    def set_value(self, value: str) -> None:
        super().set_value(value)
        self._folded = None

    @override
    def to_string(self) -> str:
        return super().to_string() if self._folded is None else self._folded
