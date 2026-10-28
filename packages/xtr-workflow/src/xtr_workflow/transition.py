"""A named move that takes tokens from some places and puts tokens in others."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

from .arc import Arc

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

__all__ = ["Transition"]


class Transition:
    """A named move that takes tokens from some places and puts tokens in others.

    Each place it leaves or enters is an :class:`Arc`; a bare place name is
    an arc of weight 1.

    Several transitions may share a name — a state machine needs one for each
    pair of places it moves between, and a workflow asked to apply a name
    applies every enabled transition of that name — so a transition is known
    by its identity, not by its name or its places: two transitions built
    alike are two transitions, each with its own metadata.
    """

    __slots__: tuple[str, ...] = ("_from_arcs", "_name", "_to_arcs")

    _name: str
    _from_arcs: tuple[Arc, ...]
    _to_arcs: tuple[Arc, ...]

    def __init__(
        self,
        name: str,
        froms: str | Arc | Sequence[str | Arc],
        tos: str | Arc | Sequence[str | Arc],
    ) -> None:
        """Name a move from ``froms`` to ``tos``.

        Args:
            name: The name the transition is applied by.
            froms: The places it takes tokens from: one place name or arc, or a
                sequence of them.
            tos: The places it puts tokens in, likewise.

        Raises:
            TypeError: If an element of ``froms`` or ``tos`` is neither a place
                name nor an arc.
            InvalidArgumentError: If a place name is empty.
        """
        self._name = name
        self._from_arcs = _arcs(froms)
        self._to_arcs = _arcs(tos)

    def get_name(self) -> str:
        """Return the name the transition is applied by."""
        return self._name

    @overload
    def get_froms(self, as_arc: Literal[False] = False) -> list[str]: ...
    @overload
    def get_froms(self, as_arc: Literal[True]) -> list[Arc]: ...
    @overload
    def get_froms(self, as_arc: bool) -> list[str] | list[Arc]: ...
    def get_froms(self, as_arc: bool = False) -> list[str] | list[Arc]:
        """Return the places the transition takes tokens from, in the order given.

        Args:
            as_arc: Return the arcs, weights included, rather than the place names.
        """
        if as_arc:
            return list(self._from_arcs)
        return [arc.place for arc in self._from_arcs]

    @overload
    def get_tos(self, as_arc: Literal[False] = False) -> list[str]: ...
    @overload
    def get_tos(self, as_arc: Literal[True]) -> list[Arc]: ...
    @overload
    def get_tos(self, as_arc: bool) -> list[str] | list[Arc]: ...
    def get_tos(self, as_arc: bool = False) -> list[str] | list[Arc]:
        """Return the places the transition puts tokens in, in the order given.

        Args:
            as_arc: Return the arcs, weights included, rather than the place names.
        """
        if as_arc:
            return list(self._to_arcs)
        return [arc.place for arc in self._to_arcs]


def _arcs(places: str | Arc | Iterable[str | Arc]) -> tuple[Arc, ...]:
    """Return ``places`` as arcs: one for a single place, one per element of a sequence."""
    if isinstance(places, str | Arc):
        return (_arc(places),)
    return tuple(_arc(place) for place in places)


def _arc(place: object) -> Arc:
    """Return ``place`` as an arc, a bare place name weighing 1.

    Typed loosely on purpose: a caller ignoring the annotations can hand over
    anything, and this is where it is refused.

    Raises:
        TypeError: If ``place`` is neither a place name nor an arc.
    """
    match place:
        case Arc():
            return place
        case str():
            return Arc(place)
        case _:
            raise TypeError(
                f'The type of arc is invalid. Expected string or Arc, got "{type(place).__name__}".'
            )
