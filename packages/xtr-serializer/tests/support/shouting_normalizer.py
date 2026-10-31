"""A normalizer decorating the declared one: what it writes, it writes in capitals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, final

from typing_extensions import override
from xtr_dependency_injection import AutowireDecorated

from tests.support.declared_normalizer import DeclaredNormalizer

if TYPE_CHECKING:
    from xtr_serializer import Context, NormalizedValue

__all__ = ["ShoutingNormalizer"]


@final
class ShoutingNormalizer(DeclaredNormalizer):
    """Writes what the normalizer it decorates writes, in capitals.

    A decorator is provided as what it decorates, so it subclasses the declared normalizer — and
    with it the interfaces the container tags a normalizer by, as it tags the normalizer it
    decorates: a test tells by the capitals that the serializer holds the decorated normalizer
    once, rather than the decorator as a normalizer of its own.
    """

    __slots__ = ("_inner",)

    def __init__(self, inner: Annotated[DeclaredNormalizer, AutowireDecorated()]) -> None:
        self._inner = inner

    @override
    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        written = self._inner.normalize(data, format, context, type_=type_)
        return written.upper() if isinstance(written, str) else written
