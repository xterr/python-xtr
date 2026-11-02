"""A normalizer declaring the interfaces it implements, as the bundle's autoconfiguration reads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, TypeVar, overload

from typing_extensions import override

from xtr_serializer import DenormalizerInterface, NormalizerInterface

if TYPE_CHECKING:
    from xtr_serializer import Context, NormalizedValue, SupportedTypes

__all__ = ["DECLARED", "DeclaredNormalizer"]

_T = TypeVar("_T")

DECLARED: Final = "declared"
"""What the declared normalizer writes for every value, and reads every data back as."""


class DeclaredNormalizer(NormalizerInterface, DenormalizerInterface):
    """Writes every value as :data:`DECLARED`, and reads any data back as it.

    It subclasses both interfaces, rather than only matching them, so the container tags it as a
    normalizer without being told to; what it writes tells a test it was picked. It is left open
    for a decorator of it, which the container provides as it.
    """

    @override
    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        del data, format, context, type_
        return DECLARED

    @override
    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> bool:
        del data, format, context, type_
        return True

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

    @override
    def denormalize(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> object:
        del data, type_, format, context
        return DECLARED

    @override
    def supports_denormalization(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        del data, type_, format, context
        return True

    @override
    def get_supported_types(self, format: str | None) -> SupportedTypes:
        del format
        return {"*": True}
