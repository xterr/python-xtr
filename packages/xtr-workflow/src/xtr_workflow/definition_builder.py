"""Assembling a definition a step at a time."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from .definition import Definition

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .metadata import MetadataStoreInterface
    from .transition import Transition

__all__ = ["DefinitionBuilder"]


class DefinitionBuilder:
    """Assembles a definition a step at a time, for code that finds its parts as it goes.

    Every step returns the builder, so steps chain, and :meth:`build` can be
    called as often as needed: each call builds a new definition from what
    the builder holds then. The builder checks nothing itself; the definition
    does, when it is built.
    """

    __slots__: tuple[str, ...] = ("_initial_places", "_metadata_store", "_places", "_transitions")

    _places: dict[str, str]
    _transitions: list[Transition]
    _initial_places: str | Sequence[str] | None
    _metadata_store: MetadataStoreInterface | None

    def __init__(
        self,
        places: Sequence[str] = (),
        transitions: Sequence[Transition] = (),
    ) -> None:
        """Start with ``places`` and ``transitions``, as if each was added in turn."""
        self._places = {}
        self._transitions = []
        self._initial_places = None
        self._metadata_store = None
        _ = self.add_places(places).add_transitions(transitions)

    def build(self) -> Definition:
        """Build the definition of what the builder holds.

        Raises:
            LogicError: If an initial place is not a place of the definition.
        """
        return Definition(
            list(self._places),
            self._transitions,
            self._initial_places,
            self._metadata_store,
        )

    def clear(self) -> Self:
        """Forget every place, transition, initial place and metadata store, to start over."""
        self._places = {}
        self._transitions = []
        self._initial_places = None
        self._metadata_store = None
        return self

    def set_initial_places(self, initial_places: str | Sequence[str] | None) -> Self:
        """Start a subject in ``initial_places``; ``None`` or empty starts it in the first place.

        Set them once the places are added: adding the first place makes it
        the initial place, over any set before.
        """
        self._initial_places = initial_places
        return self

    def add_place(self, place: str) -> Self:
        """Add ``place``; the first place added is the initial place until told otherwise."""
        if not self._places:
            self._initial_places = place

        self._places[place] = place
        return self

    def add_places(self, places: Sequence[str]) -> Self:
        """Add each of ``places``, in order."""
        for place in places:
            _ = self.add_place(place)
        return self

    def add_transitions(self, transitions: Sequence[Transition]) -> Self:
        """Add each of ``transitions``, in order."""
        for transition in transitions:
            _ = self.add_transition(transition)
        return self

    def add_transition(self, transition: Transition) -> Self:
        """Add ``transition``; the places it leaves or enters become places when it is built."""
        self._transitions.append(transition)
        return self

    def set_metadata_store(self, metadata_store: MetadataStoreInterface) -> Self:
        """Read the definition's metadata from ``metadata_store`` instead of an empty store."""
        self._metadata_store = metadata_store
        return self
