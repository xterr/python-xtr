"""A workflow that answers its accessors and moves nothing."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_workflow import Definition
from xtr_workflow.marking_store import MethodMarkingStore

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow import Marking, MarkingStoreInterface, Transition, TransitionBlockerList
    from xtr_workflow.metadata import MetadataStoreInterface

__all__ = ["WorkflowStub"]


@final
class WorkflowStub:
    """Stands in for a workflow where only its name, definition and stores are read.

    What an error quoting the workflow's name, or an event reading its
    metadata, needs; asking it to move a subject is a mistake in the test.
    """

    def __init__(
        self,
        name: str = "article",
        definition: Definition | None = None,
        marking_store: MarkingStoreInterface | None = None,
    ) -> None:
        self._name = name
        self._definition = definition if definition is not None else Definition([], [])
        self._marking_store = marking_store if marking_store is not None else MethodMarkingStore()

    def get_name(self) -> str:
        return self._name

    def get_definition(self) -> Definition:
        return self._definition

    def get_marking_store(self) -> MarkingStoreInterface:
        return self._marking_store

    def get_metadata_store(self) -> MetadataStoreInterface:
        return self._definition.get_metadata_store()

    async def get_marking(
        self, subject: object, context: Mapping[str, object] | None = None
    ) -> Marking:
        del subject, context
        raise NotImplementedError

    async def can(self, subject: object, transition_name: str) -> bool:
        del subject, transition_name
        raise NotImplementedError

    async def build_transition_blocker_list(
        self, subject: object, transition_name: str
    ) -> TransitionBlockerList:
        del subject, transition_name
        raise NotImplementedError

    async def apply(
        self,
        subject: object,
        transition_name: str,
        context: Mapping[str, object] | None = None,
    ) -> Marking:
        del subject, transition_name, context
        raise NotImplementedError

    async def get_enabled_transitions(self, subject: object) -> list[Transition]:
        del subject
        raise NotImplementedError

    async def get_enabled_transition(self, subject: object, name: str) -> Transition | None:
        del subject, name
        raise NotImplementedError
