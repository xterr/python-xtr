"""Where the metadata of a workflow, of its places and of its transitions is read."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow.transition import Transition

__all__ = ["MetadataStoreInterface"]


@runtime_checkable
class MetadataStoreInterface(Protocol):
    """Reads the metadata of a workflow, of its places and of its transitions.

    Metadata is what a definition carries for whoever reads it — a title a
    dump shows, a flag a listener checks — and moving a subject never looks
    at it. Each subject's metadata is a mapping of entries by name, empty for
    a subject that has none.
    """

    def get_workflow_metadata(self) -> Mapping[str, object]:
        """Return the metadata of the workflow itself."""
        ...

    def get_place_metadata(self, place: str) -> Mapping[str, object]:
        """Return the metadata of ``place``, empty when it has none."""
        ...

    def get_transition_metadata(self, transition: Transition) -> Mapping[str, object]:
        """Return the metadata of ``transition``, empty when it has none.

        A transition is known by its identity, so one built alike is another
        transition, with metadata of its own.
        """
        ...

    def get_metadata(self, key: str, subject: str | Transition | None = None) -> object | None:
        """Return one entry of the metadata of the workflow, of a place or of a transition.

        For a reader that wants a single entry and knows what it is about,
        whatever that is: the subject picks which of the three getters is read.

        Args:
            key: The name of the entry.
            subject: ``None`` for the workflow, a place name for that place, or
                a transition for that transition.

        Returns:
            The entry, or ``None`` when the subject's metadata has none by that name.

        Raises:
            InvalidArgumentError: If ``subject`` is none of the three.
        """
        ...
