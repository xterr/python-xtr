"""A normalizer for points: the smallest one that both writes and reads."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, final, overload

from tests.support.shapes import Point
from xtr_serializer.exception import InvalidArgumentError, NotNormalizableValueError

if TYPE_CHECKING:
    from xtr_serializer import Context, NormalizedValue, SupportedTypes

__all__ = ["PointNormalizer"]

_T = TypeVar("_T")


@final
class PointNormalizer:
    """Writes a point as ``{"x": ..., "y": ...}`` and reads that back into a point."""

    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        del format, context, type_
        if not isinstance(data, Point):
            raise InvalidArgumentError("only a point is normalized here")
        return {"x": data.x, "y": data.y}

    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> bool:
        del format, context, type_
        return isinstance(data, Point)

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
        del format, context
        if type_ is not Point:
            raise InvalidArgumentError("only a point is denormalized here")
        match data:
            case {"x": int() as x, "y": int() as y}:
                return Point(x, y)
            case _:
                raise NotNormalizableValueError(
                    "a point needs an integer x and y",
                    expected_types=("Point",),
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
        return type_ is Point

    def get_supported_types(self, format: str | None) -> SupportedTypes:
        del format
        return {Point: True}
