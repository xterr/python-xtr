"""Metadata kept in this process's memory, as the definition was given it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .get_metadata_trait import GetMetadataTrait

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow.transition import Transition

__all__ = ["InMemoryMetadataStore"]


@final
class InMemoryMetadataStore(GetMetadataTrait):
    """Keeps the metadata of a workflow, of its places and of its transitions in dictionaries.

    The store a definition gets when it is given none. A transition's
    metadata is keyed by the transition itself, not by its name: several
    transitions can share a name, and each has metadata of its own.

    Each mapping it is built with is copied, and so is each mapping it
    returns, so changing one never reaches the store, however many workflows
    share it.
    """

    _workflow_metadata: dict[str, object]
    _places_metadata: dict[str, dict[str, object]]
    _transitions_metadata: dict[Transition, dict[str, object]]

    def __init__(
        self,
        workflow_metadata: Mapping[str, object] | None = None,
        places_metadata: Mapping[str, Mapping[str, object]] | None = None,
        transitions_metadata: Mapping[Transition, Mapping[str, object]] | None = None,
    ) -> None:
        """Keep the metadata of the workflow, of each place and of each transition.

        Args:
            workflow_metadata: The entries of the workflow itself.
            places_metadata: The entries of each place, by place name.
            transitions_metadata: The entries of each transition, by transition.
        """
        self._workflow_metadata = dict(workflow_metadata or {})
        self._places_metadata = {
            place: dict(metadata) for place, metadata in (places_metadata or {}).items()
        }
        self._transitions_metadata = {
            transition: dict(metadata)
            for transition, metadata in (transitions_metadata or {}).items()
        }

    @override
    def get_workflow_metadata(self) -> dict[str, object]:
        """Return the metadata of the workflow itself."""
        return dict(self._workflow_metadata)

    @override
    def get_place_metadata(self, place: str) -> dict[str, object]:
        """Return the metadata of ``place``, empty when it has none."""
        return dict(self._places_metadata.get(place, {}))

    @override
    def get_transition_metadata(self, transition: Transition) -> dict[str, object]:
        """Return the metadata of ``transition``, empty when it has none."""
        return dict(self._transitions_metadata.get(transition, {}))
