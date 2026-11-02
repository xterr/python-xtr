"""The first of a serializer's normalizers to handle a type, asked about it only as needed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Protocol, TypeVar, final

from ._type_cache import TypeCache

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from .supported_types import SupportedTypes

__all__ = ["Dispatch"]


class _ReportingTypes(Protocol):
    """What tells the types it handles: a normalizer or a denormalizer."""

    def get_supported_types(self, format: str | None, /) -> SupportedTypes: ...  # noqa: A002 — the name every serializer call uses.


_C = TypeVar("_C", bound=_ReportingTypes)


@final
class Dispatch(Generic[_C]):
    """Finds the first of some normalizers, in the order given, that handles a type in a format.

    The types each reports for the format say which to ask at all, and which answers to keep:
    for each type and format, a dispatch remembers the normalizers that may handle it, in order,
    with the answer of each whose answer rests on the type alone. A normalizer for which it is
    ``None`` is never asked, nor one no key covers. One whose answer rests on the type alone is
    asked once: answering yes, it is the one for that type, and those after it are never asked;
    answering no, it is not asked again. Any other is asked every time.

    Threads may share a dispatch; the answers are kept in a :class:`TypeCache`. Two threads
    looking a type up for the first time at once may both ask the normalizers.
    """

    __slots__ = ("_candidates", "_chains")

    def __init__(self, candidates: Sequence[_C]) -> None:
        self._candidates = tuple(candidates)
        self._chains: TypeCache[tuple[tuple[_C, bool], ...]] = TypeCache()

    def first(
        self,
        type_: object,
        format: str | None,  # noqa: A002 — the name every serializer call uses.
        supports: Callable[[_C], bool],
    ) -> _C | None:
        """Return the first normalizer ``supports`` says handles ``type_`` in ``format``, if any.

        ``supports`` asks one normalizer about the value at hand, and is only called when its
        answer is not known.
        """
        chain = self._chains.get(type_, lambda: self._chain(type_, format, supports), format)
        for candidate, settled in chain:
            if settled or supports(candidate):
                return candidate
        return None

    def _chain(
        self,
        type_: object,
        format: str | None,  # noqa: A002 — the name every serializer call uses.
        supports: Callable[[_C], bool],
    ) -> tuple[tuple[_C, bool], ...]:
        """Give the normalizers that may handle ``type_``, each with whether it surely does."""
        chain: list[tuple[_C, bool]] = []
        for candidate in self._candidates:
            answer = _answer_for(candidate.get_supported_types(format), type_)
            if answer is None:
                continue
            if not answer:
                chain.append((candidate, False))
            elif supports(candidate):
                chain.append((candidate, True))
                break
        return tuple(chain)


def _answer_for(supported: SupportedTypes, type_: object) -> bool | None:
    """Give what ``supported`` says of ``type_``: by its own key, its class's, then a broader one.

    ``None`` when ``type_`` is not handled. A key naming a class covers its subclasses; the first
    such key, in the order reported, counts. ``"object"`` covers every class, but no other type
    expression; ``"*"`` covers anything.
    """
    if not isinstance(type_, type):
        return supported.get("*")
    classes = [key for key in supported if isinstance(key, type)]
    for key in classes:
        if key is type_:
            return supported[key]
    for key in classes:
        if issubclass(type_, key):
            return supported[key]
    if "object" in supported:
        return supported["object"]
    return supported.get("*")
