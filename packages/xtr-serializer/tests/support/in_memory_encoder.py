"""An encoder that keeps what it is given and writes a reference to it."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Final, final

from xtr_serializer.exception import NotEncodableValueError

if TYPE_CHECKING:
    from xtr_serializer import Context, NormalizedValue

__all__ = ["MEMORY", "InMemoryEncoder"]

MEMORY: Final = "memory"
"""The one format the in-memory encoder writes and reads."""


@final
class InMemoryEncoder:
    """Writes plain data as a reference to a copy it keeps, and reads a reference back.

    A stand-in for a real format: the text says nothing about the data, so a test sees the
    encoder was used without depending on how a real format spells a value — and every value
    comes back equal, which is all an encoder promises. References count up from ``#1`` in the
    order the values were written.
    """

    __slots__ = ("_kept",)

    def __init__(self) -> None:
        self._kept: dict[str, NormalizedValue] = {}

    def encode(
        self,
        data: NormalizedValue,
        format: str,
        context: Context | None = None,
    ) -> str:
        del format, context
        reference = f"#{len(self._kept) + 1}"
        self._kept[reference] = copy.deepcopy(data)
        return reference

    def supports_encoding(self, format: str) -> bool:
        return format == MEMORY

    def decode(
        self,
        data: str | bytes,
        format: str,
        context: Context | None = None,
    ) -> NormalizedValue:
        del format, context
        reference = data.decode(errors="replace") if isinstance(data, bytes) else data
        if reference not in self._kept:
            raise NotEncodableValueError("the text is not a reference this encoder wrote")
        return copy.deepcopy(self._kept[reference])

    def supports_decoding(self, format: str) -> bool:
        return format == MEMORY
