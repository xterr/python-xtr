"""A normalizer for parcels, which has the serializer it is handed write their content."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, final, overload

from tests.support.shapes import Parcel, Point
from xtr_serializer.exception import InvalidArgumentError, LogicError, NotNormalizableValueError

if TYPE_CHECKING:
    from xtr_serializer import Context, NormalizedValue, SerializerInterface, SupportedTypes

__all__ = ["ParcelNormalizer"]

_T = TypeVar("_T")


@final
class ParcelNormalizer:
    """Writes a parcel with its point already serialized, as text inside the parcel's data.

    The shape of a normalizer that needs the whole serializer rather than the next normalizer:
    what it embeds is finished text, in a format of its own.
    """

    __slots__ = ("_content_format", "_serializer")

    def __init__(self, content_format: str) -> None:
        self._content_format = content_format
        self._serializer: SerializerInterface | None = None

    def set_serializer(self, serializer: SerializerInterface, /) -> None:
        self._serializer = serializer

    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        del format, type_
        if not isinstance(data, Parcel):
            raise InvalidArgumentError("only a parcel is normalized here")
        serializer = self._serializer_in_use()
        return {"content": serializer.serialize(data.content, self._content_format, context)}

    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> bool:
        del format, context, type_
        return isinstance(data, Parcel)

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
        del format
        if type_ is not Parcel:
            raise InvalidArgumentError("only a parcel is denormalized here")
        match data:
            case {"content": str() as content}:
                serializer = self._serializer_in_use()
                return Parcel(serializer.deserialize(content, Point, self._content_format, context))
            case _:
                raise NotNormalizableValueError(
                    "a parcel needs its content as text",
                    expected_types=("Parcel",),
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
        return type_ is Parcel

    def get_supported_types(self, format: str | None) -> SupportedTypes:
        del format
        return {Parcel: True}

    def _serializer_in_use(self) -> SerializerInterface:
        if self._serializer is None:
            raise LogicError("the parcel normalizer was handed no serializer")
        return self._serializer
