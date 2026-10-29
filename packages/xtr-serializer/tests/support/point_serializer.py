"""A serializer for points, made of the point normalizer and the in-memory encoder."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, final, overload

from tests.support.in_memory_encoder import InMemoryEncoder
from tests.support.point_normalizer import PointNormalizer
from xtr_serializer.exception import UnsupportedFormatError

if TYPE_CHECKING:
    from xtr_serializer import Context

__all__ = ["PointSerializer"]

_T = TypeVar("_T")


@final
class PointSerializer:
    """Serializes points through one normalizer and one encoder.

    A serializer at its smallest, for code that is handed a serializer and needs one that
    works: it writes and reads points, in the in-memory format only.
    """

    __slots__ = ("_encoder", "_normalizer")

    def __init__(self) -> None:
        self._normalizer = PointNormalizer()
        self._encoder = InMemoryEncoder()

    def serialize(
        self,
        data: object,
        format: str,
        context: Context | None = None,
    ) -> str:
        if not self._encoder.supports_encoding(format):
            raise UnsupportedFormatError(format)
        normalized = self._normalizer.normalize(data, format, context)
        return self._encoder.encode(normalized, format, context)

    @overload
    def deserialize(
        self,
        data: str | bytes,
        type_: type[_T],
        format: str,
        context: Context | None = None,
    ) -> _T: ...

    @overload
    def deserialize(
        self,
        data: str | bytes,
        type_: object,
        format: str,
        context: Context | None = None,
    ) -> object: ...

    def deserialize(
        self,
        data: str | bytes,
        type_: object,
        format: str,
        context: Context | None = None,
    ) -> object:
        if not self._encoder.supports_decoding(format):
            raise UnsupportedFormatError(format)
        normalized = self._encoder.decode(data, format, context)
        return self._normalizer.denormalize(normalized, type_, format, context)
