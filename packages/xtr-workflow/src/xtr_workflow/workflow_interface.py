"""Moving a subject through a definition, and telling which moves are open to it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .definition import Definition
    from .marking import Marking
    from .marking_store import MarkingStoreInterface
    from .metadata import MetadataStoreInterface
    from .transition import Transition
    from .transition_blocker_list import TransitionBlockerList

__all__ = ["WorkflowInterface"]


@runtime_checkable
class WorkflowInterface(Protocol):
    """Applies transitions to a subject, and tells which ones are enabled or blocked.

    Everything that may ask listeners — reading a marking for the first time,
    checking or applying a transition — is a coroutine, because the events
    it dispatches are awaited; what only reads the workflow itself is not.
    """

    async def get_marking(
        self, subject: object, context: Mapping[str, object] | None = None
    ) -> Marking:
        """Return the marking ``subject`` is in.

        A subject in no place yet is put in the initial places first, and an
        ``entered`` event announces it.

        Args:
            subject: The object the workflow moves.
            context: The context of that ``entered`` event.

        Raises:
            LogicError: If the subject is in no place and the definition has
                no initial place, or it is in a place the definition lacks.
        """
        ...

    async def can(self, subject: object, transition_name: str) -> bool:
        """Tell whether a transition named ``transition_name`` is enabled for ``subject``."""
        ...

    async def build_transition_blocker_list(
        self, subject: object, transition_name: str
    ) -> TransitionBlockerList:
        """Return why the transition named ``transition_name`` is blocked; empty when it is not.

        Raises:
            UndefinedTransitionError: If no transition has that name.
        """
        ...

    async def apply(
        self,
        subject: object,
        transition_name: str,
        context: Mapping[str, object] | None = None,
    ) -> Marking:
        """Apply every enabled transition named ``transition_name`` to ``subject``.

        Args:
            subject: The object to move.
            transition_name: The name of the transition.
            context: Handed to every event and to the marking store.

        Returns:
            The marking the subject is in afterwards.

        Raises:
            LogicError: If the transition cannot be applied — it is undefined,
                or blocked.
        """
        ...

    async def get_enabled_transitions(self, subject: object) -> list[Transition]:
        """Return every transition enabled for ``subject``."""
        ...

    async def get_enabled_transition(self, subject: object, name: str) -> Transition | None:
        """Return the first transition named ``name`` enabled for ``subject``, or ``None``."""
        ...

    def get_name(self) -> str:
        """Return the name of the workflow."""
        ...

    def get_definition(self) -> Definition:
        """Return the places and transitions the workflow moves subjects through."""
        ...

    def get_marking_store(self) -> MarkingStoreInterface:
        """Return where the workflow reads and writes each subject's marking."""
        ...

    def get_metadata_store(self) -> MetadataStoreInterface:
        """Return where the metadata of the workflow, its places and its transitions is read."""
        ...
