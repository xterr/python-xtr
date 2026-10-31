"""An encoder declaring the interfaces it implements, as the bundle's autoconfiguration reads."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from tests.support.in_memory_encoder import InMemoryEncoder
from xtr_serializer import DecoderInterface, EncoderInterface

if TYPE_CHECKING:
    from xtr_serializer import Context, NormalizedValue

__all__ = ["DeclaredEncoder"]


@final
class DeclaredEncoder(EncoderInterface, DecoderInterface):
    """The in-memory encoder, subclassing both interfaces rather than only matching them.

    So the container tags it as an encoder without being told to.
    """

    __slots__ = ("_kept",)

    def __init__(self) -> None:
        self._kept = InMemoryEncoder()

    @override
    def encode(self, data: NormalizedValue, format: str, context: Context | None = None) -> str:
        return self._kept.encode(data, format, context)

    @override
    def supports_encoding(self, format: str) -> bool:
        return self._kept.supports_encoding(format)

    @override
    def decode(
        self, data: str | bytes, format: str, context: Context | None = None
    ) -> NormalizedValue:
        return self._kept.decode(data, format, context)

    @override
    def supports_decoding(self, format: str) -> bool:
        return self._kept.supports_decoding(format)
