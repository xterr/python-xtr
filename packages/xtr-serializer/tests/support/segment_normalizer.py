"""A normalizer for segments, which hands each point to the normalizer it is given."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, final, overload

from tests.support.shapes import Point, Segment
from xtr_serializer.exception import InvalidArgumentError, LogicError, NotNormalizableValueError

if TYPE_CHECKING:
    from xtr_serializer import (
        Context,
        DenormalizerInterface,
        NormalizedValue,
        NormalizerInterface,
        SupportedTypes,
    )

__all__ = ["SegmentNormalizer"]

_T = TypeVar("_T")


@final
class SegmentNormalizer:
    """Writes a segment as its two points, each written by the normalizer it is handed.

    The shape of a normalizer for an object made of other objects: it knows the segment and
    leaves the points to whatever it is handed — in a serializer, the serializer itself.
    """

    __slots__ = ("_denormalizer", "_normalizer")

    def __init__(self) -> None:
        self._normalizer: NormalizerInterface | None = None
        self._denormalizer: DenormalizerInterface | None = None

    def set_normalizer(self, normalizer: NormalizerInterface, /) -> None:
        self._normalizer = normalizer

    def set_denormalizer(self, denormalizer: DenormalizerInterface, /) -> None:
        self._denormalizer = denormalizer

    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        del type_
        if not isinstance(data, Segment):
            raise InvalidArgumentError("only a segment is normalized here")
        if self._normalizer is None:
            raise LogicError("the segment normalizer was handed no normalizer for its points")
        return {
            "start": self._normalizer.normalize(data.start, format, context),
            "end": self._normalizer.normalize(data.end, format, context),
        }

    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> bool:
        del format, context, type_
        return isinstance(data, Segment)

    @overload
    def denormalize(
        self,
        data: object,
        type_: type[_T],
        format: str | None = None,
        context: Context | None = None,
    ) -> _T: ...

    @overload
    def denormalize(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> object: ...

    def denormalize(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> object:
        if type_ is not Segment:
            raise InvalidArgumentError("only a segment is denormalized here")
        if self._denormalizer is None:
            raise LogicError("the segment normalizer was handed no denormalizer for its points")
        match data:
            case {"start": object() as start, "end": object() as end}:
                return Segment(
                    self._denormalizer.denormalize(start, Point, format, context),
                    self._denormalizer.denormalize(end, Point, format, context),
                )
            case _:
                raise NotNormalizableValueError(
                    "a segment needs a start and an end",
                    expected_types=("Segment",),
                    current_type=type(data).__name__,
                )

    def supports_denormalization(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        del data, format, context
        return type_ is Segment

    def get_supported_types(self, format: str | None) -> SupportedTypes:
        del format
        return {Segment: True}
