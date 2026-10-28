"""The places a subject can be in, and the transitions that move it between them."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .exception import LogicError
from .metadata import InMemoryMetadataStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .metadata import MetadataStoreInterface
    from .transition import Transition

__all__ = ["Definition"]


@final
class Definition:
    """The places a subject can be in, and the transitions that move it between them.

    A place a transition leaves or enters is a place of the definition even
    when it is not among the places given, so no transition leads nowhere.
    Places keep the order they first appear in — those given, then those the
    transitions bring — which is the order a dump draws them in.

    A subject starts in the initial places, the first place unless told
    otherwise; a definition with no place has none. Nothing changes once it
    is built: what it returns is a copy.
    """

    __slots__: tuple[str, ...] = ("_initial_places", "_metadata_store", "_places", "_transitions")

    _places: dict[str, str]
    _transitions: list[Transition]
    _initial_places: list[str]
    _metadata_store: MetadataStoreInterface

    def __init__(
        self,
        places: Sequence[str],
        transitions: Sequence[Transition],
        initial_places: str | Sequence[str] | None = None,
        metadata_store: MetadataStoreInterface | None = None,
    ) -> None:
        """Define ``places`` and ``transitions``, a subject starting in ``initial_places``.

        Args:
            places: The places, in the order they are drawn.
            transitions: The transitions; a place one leaves or enters that is
                not among ``places`` is added after them.
            initial_places: The place, or places, a subject starts in; the
                first place when ``None`` or empty.
            metadata_store: Where the metadata of the workflow, of its places
                and of its transitions is read; an empty in-memory store when
                ``None``.

        Raises:
            LogicError: If an initial place is not a place of the definition.
        """
        self._places = {}
        self._transitions = []
        self._initial_places = []
        for place in places:
            self._add_place(place)
        for transition in transitions:
            self._add_transition(transition)
        self._set_initial_places(initial_places)
        self._metadata_store = InMemoryMetadataStore() if metadata_store is None else metadata_store

    def get_initial_places(self) -> list[str]:
        """Return the places a subject starts in, empty when there is no place."""
        return list(self._initial_places)

    def get_places(self) -> dict[str, str]:
        """Return every place, keyed by its own name, in the order they first appeared.

        Keyed so that a place can be looked up as well as listed.
        """
        return dict(self._places)

    def get_transitions(self) -> list[Transition]:
        """Return the transitions, in the order they were given."""
        return list(self._transitions)

    def get_metadata_store(self) -> MetadataStoreInterface:
        """Return where the metadata of the workflow, its places and its transitions is read."""
        return self._metadata_store

    def _set_initial_places(self, places: str | Sequence[str] | None) -> None:
        """Start a subject in ``places``, keeping the first place when there are none.

        Raises:
            LogicError: If one of ``places`` is not a place of the definition.
        """
        if not places:
            return

        initial_places = [places] if isinstance(places, str) else list(places)
        for place in initial_places:
            if place not in self._places:
                raise LogicError(
                    f'Place "{place}" cannot be the initial place as it does not exist.'
                )

        self._initial_places = initial_places

    def _add_place(self, place: str) -> None:
        """Add ``place``; the first place added is where a subject starts until told otherwise."""
        if not self._places:
            self._initial_places = [place]

        self._places[place] = place

    def _add_transition(self, transition: Transition) -> None:
        """Add ``transition``, and every place it leaves or enters that is not a place yet."""
        for place in (*transition.get_froms(), *transition.get_tos()):
            self._add_place(place)

        self._transitions.append(transition)
