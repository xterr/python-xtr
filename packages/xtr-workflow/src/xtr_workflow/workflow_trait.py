"""Letting a class that declares a workflow be used as that workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .exception import LogicError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .definition import Definition
    from .marking import Marking
    from .marking_store import MarkingStoreInterface
    from .metadata import MetadataStoreInterface
    from .transition import Transition
    from .transition_blocker_list import TransitionBlockerList
    from .workflow_interface import WorkflowInterface

__all__ = ["WorkflowTrait"]


class WorkflowTrait:
    """Exposes every method of a workflow on the class that mixes this in.

    Meant for a class decorated with ``@as_workflow``: the class declares the
    workflow and its listeners, and, once handed the workflow built from that
    declaration, answers for it — so the code moving subjects depends on one
    class carrying both its own helpers and the workflow's methods. The class
    keeps any constructor it likes; the workflow comes through
    :meth:`set_workflow`, which the workflow bundle calls after building it.

    The workflow is kept under a name-mangled attribute, so a class mixing
    this in is free to use ``_workflow`` for anything of its own.
    """

    if TYPE_CHECKING:
        # Annotated for the type checker only: the workflow bundle reads the
        # annotations of a workflow class and its bases at runtime, where the
        # interface named here is not imported.
        __workflow: WorkflowInterface | None

    __workflow = None

    def set_workflow(self, workflow: WorkflowInterface) -> None:
        """Answer for ``workflow`` from now on."""
        self.__workflow = workflow

    async def get_marking(
        self, subject: object, context: Mapping[str, object] | None = None
    ) -> Marking:
        """Return the marking ``subject`` is in; see :meth:`WorkflowInterface.get_marking`."""
        return await self.__required().get_marking(subject, context)

    async def can(self, subject: object, transition_name: str) -> bool:
        """Tell whether a transition named ``transition_name`` is enabled for ``subject``."""
        return await self.__required().can(subject, transition_name)

    async def build_transition_blocker_list(
        self, subject: object, transition_name: str
    ) -> TransitionBlockerList:
        """Return why the transition named ``transition_name`` is blocked; empty when it is not."""
        return await self.__required().build_transition_blocker_list(subject, transition_name)

    async def apply(
        self,
        subject: object,
        transition_name: str,
        context: Mapping[str, object] | None = None,
    ) -> Marking:
        """Apply every enabled transition named ``transition_name`` to ``subject``."""
        return await self.__required().apply(subject, transition_name, context)

    async def get_enabled_transitions(self, subject: object) -> list[Transition]:
        """Return every transition enabled for ``subject``."""
        return await self.__required().get_enabled_transitions(subject)

    async def get_enabled_transition(self, subject: object, name: str) -> Transition | None:
        """Return the first transition named ``name`` enabled for ``subject``, or ``None``."""
        return await self.__required().get_enabled_transition(subject, name)

    def get_name(self) -> str:
        """Return the name of the workflow."""
        return self.__required().get_name()

    def get_definition(self) -> Definition:
        """Return the places and transitions the workflow moves subjects through."""
        return self.__required().get_definition()

    def get_marking_store(self) -> MarkingStoreInterface:
        """Return where the workflow reads and writes each subject's marking."""
        return self.__required().get_marking_store()

    def get_metadata_store(self) -> MetadataStoreInterface:
        """Return where the metadata of the workflow, its places and its transitions is read."""
        return self.__required().get_metadata_store()

    def __required(self) -> WorkflowInterface:
        """Return the workflow handed to :meth:`set_workflow`.

        Raises:
            LogicError: If none was yet: the class was built by hand and never
                given one, which nothing could answer for in its place.
        """
        if self.__workflow is None:
            owner = type(self)
            raise LogicError(
                f'"{owner.__module__}.{owner.__qualname__}" has no workflow yet: '
                "call set_workflow() before using it."
            )
        return self.__workflow
