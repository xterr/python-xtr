"""A normalizer that counts how often it is asked whether it handles a value, and records calls."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, final, overload

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_serializer import Context, NormalizedValue, SupportedTypes

__all__ = ["CountingNormalizer"]

_T = TypeVar("_T")


@final
class CountingNormalizer:
    """Writes every value it is handed as its name, and reads any data back as its name.

    For a test of how a serializer picks a normalizer: the result tells which one it picked, the
    counts tell how often it asked, and the records tell what each call was handed. The types it
    reports are given per format; a format it is given none for, it reports none in.
    """

    __slots__ = ("asked", "calls", "handles", "name", "supported")

    def __init__(
        self,
        name: str,
        supported: Mapping[str | None, SupportedTypes],
        *,
        handles: bool = True,
    ) -> None:
        self.name = name
        self.supported = supported
        self.handles = handles
        self.asked = 0
        self.calls: list[tuple[Context | None, object]] = []

    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        del data, format
        self.calls.append((context, type_))
        return self.name

    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> bool:
        del data, format, context, type_
        self.asked += 1
        return self.handles

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
        del data, format
        self.calls.append((context, type_))
        return self.name

    def supports_denormalization(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        del data, type_, format, context
        self.asked += 1
        return self.handles

    def get_supported_types(self, format: str | None) -> SupportedTypes:
        return self.supported.get(format, {})
