"""Moving a subject through a definition, with listeners asked and told at every step."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from typing_extensions import override

from ._events_to_dispatch import events_to_dispatch_from
from .event import (
    AnnounceEvent,
    CompletedEvent,
    EnteredEvent,
    EnterEvent,
    GuardEvent,
    LeaveEvent,
    TransitionEvent,
)
from .exception import (
    LogicError,
    NotEnabledTransitionError,
    UndefinedTransitionError,
)
from .marking_store import MethodMarkingStore
from .transition_blocker import TransitionBlocker
from .transition_blocker_list import TransitionBlockerList
from .workflow_events import WorkflowEvents
from .workflow_interface import WorkflowInterface

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface

    from .definition import Definition
    from .event import Event
    from .marking import Marking
    from .marking_store import MarkingStoreInterface
    from .metadata import MetadataStoreInterface
    from .transition import Transition

__all__ = ["Workflow"]


class Workflow(WorkflowInterface):
    """Moves a subject through a definition: a Petri net, where it can be in several places.

    A transition is enabled when every place it leaves holds the tokens it
    takes, and no guard listener blocks it. Applying a name applies every
    transition of that name enabled at that moment, so a subject spread over
    several places can move out of all of them at once.

    Each step goes out as an event, under three names — for every workflow,
    for this one, and for the place or transition concerned — so listeners
    hear exactly what they care about: ``guard`` before a transition is
    applied or reported enabled, then, while applying it, ``leave``,
    ``transition`` (where a listener may replace the call's context),
    ``enter``, ``entered``, ``completed`` and ``announce``. Without a
    dispatcher, nothing is asked and nothing told.
    """

    DISABLE_LEAVE_EVENT: Final[str] = "workflow_disable_leave_event"
    """A true value under this context key keeps the call from dispatching ``leave``."""

    DISABLE_TRANSITION_EVENT: Final[str] = "workflow_disable_transition_event"
    """A true value under this context key keeps the call from dispatching ``transition``."""

    DISABLE_ENTER_EVENT: Final[str] = "workflow_disable_enter_event"
    """A true value under this context key keeps the call from dispatching ``enter``."""

    DISABLE_ENTERED_EVENT: Final[str] = "workflow_disable_entered_event"
    """A true value under this context key keeps the call from dispatching ``entered``."""

    DISABLE_COMPLETED_EVENT: Final[str] = "workflow_disable_completed_event"
    """A true value under this context key keeps the call from dispatching ``completed``."""

    DISABLE_ANNOUNCE_EVENT: Final[str] = "workflow_disable_announce_event"
    """A true value under this context key keeps the call from dispatching ``announce``."""

    DEFAULT_INITIAL_CONTEXT: Final[Mapping[str, object]] = MappingProxyType({"initial": True})
    """The context of the ``entered`` event putting a subject in its initial places, when the
    call gave none — so a listener can tell a subject's first marking from a move."""

    _DISABLE_EVENTS_MAPPING: Final[Mapping[str, str]] = MappingProxyType(
        {
            WorkflowEvents.LEAVE: DISABLE_LEAVE_EVENT,
            WorkflowEvents.TRANSITION: DISABLE_TRANSITION_EVENT,
            WorkflowEvents.ENTER: DISABLE_ENTER_EVENT,
            WorkflowEvents.ENTERED: DISABLE_ENTERED_EVENT,
            WorkflowEvents.COMPLETED: DISABLE_COMPLETED_EVENT,
            WorkflowEvents.ANNOUNCE: DISABLE_ANNOUNCE_EVENT,
        }
    )

    __slots__: tuple[str, ...] = (
        "_definition",
        "_dispatcher",
        "_events_to_dispatch",
        "_marking_store",
        "_name",
    )

    _definition: Definition
    _marking_store: MarkingStoreInterface
    _dispatcher: EventDispatcherInterface | None
    _name: str
    _events_to_dispatch: frozenset[str] | None

    def __init__(
        self,
        definition: Definition,
        marking_store: MarkingStoreInterface | None = None,
        dispatcher: EventDispatcherInterface | None = None,
        name: str = "unnamed",
        events_to_dispatch: Sequence[str] | None = None,
    ) -> None:
        """Move subjects through ``definition``, keeping their markings in ``marking_store``.

        Args:
            definition: The places and transitions.
            marking_store: Where each subject's marking is kept; on the subject,
                as a dict of places, when ``None``.
            dispatcher: Where the events go; none is dispatched without one.
            name: The name of the workflow, narrowing the events' names.
            events_to_dispatch: Which of the :class:`WorkflowEvents` go out
                besides the guard, which always does: every one when ``None``,
                none when empty, only those listed, or — when every entry
                starts with ``!`` — every one but those listed, so an event
                added later goes out too.

        Raises:
            InvalidArgumentError: If ``events_to_dispatch`` mixes listed and
                ``!``-prefixed entries, or blocks the guard.
        """
        self._definition = definition
        self._marking_store = MethodMarkingStore() if marking_store is None else marking_store
        self._dispatcher = dispatcher
        self._name = name
        self._events_to_dispatch = (
            None
            if events_to_dispatch is None
            else events_to_dispatch_from(events_to_dispatch, name)
        )

    @override
    async def get_marking(
        self, subject: object, context: Mapping[str, object] | None = None
    ) -> Marking:
        marking = await self._marking_store.get_marking(subject)

        if not marking.get_places():
            initial_places = self._definition.get_initial_places()
            if not initial_places:
                raise LogicError(
                    "The Marking is empty and there is no initial place for workflow "
                    f'"{self._name}".'
                )
            for place in initial_places:
                marking.mark(place)

            await self._marking_store.set_marking(subject, marking)
            await self._entered(subject, None, marking, context or self.DEFAULT_INITIAL_CONTEXT)

        places = self._definition.get_places()
        for place in marking.get_places():
            if place not in places:
                message = f'Place "{place}" is not valid for workflow "{self._name}".'
                if not places:
                    message += " It seems you forgot to add places to the current workflow."
                raise LogicError(message)

        return marking

    @override
    async def can(self, subject: object, transition_name: str) -> bool:
        marking = await self.get_marking(subject)

        for transition in self._transitions_named(transition_name):
            blockers = await self._build_transition_blocker_list_for(subject, marking, transition)
            if blockers.is_empty():
                return True

        return False

    @override
    async def build_transition_blocker_list(
        self, subject: object, transition_name: str
    ) -> TransitionBlockerList:
        marking = await self.get_marking(subject)
        blockers: TransitionBlockerList | None = None

        for transition in self._transitions_named(transition_name):
            blockers = await self._build_transition_blocker_list_for(subject, marking, transition)
            # Blocked by anything but the marking means the marking was right: of
            # the transitions sharing a name, that is the one worth explaining.
            if blockers.is_empty() or not blockers.has(TransitionBlocker.BLOCKED_BY_MARKING):
                return blockers

        if blockers is None:
            raise UndefinedTransitionError(subject, transition_name, self)

        return blockers

    @override
    async def apply(
        self,
        subject: object,
        transition_name: str,
        context: Mapping[str, object] | None = None,
    ) -> Marking:
        call_context: dict[str, object] = dict(context) if context is not None else {}
        marking = await self.get_marking(subject, call_context)

        approved_transitions: list[Transition] = []
        best_blockers: TransitionBlockerList | None = None
        for transition in self._transitions_named(transition_name):
            blockers = await self._build_transition_blocker_list_for(subject, marking, transition)
            if blockers.is_empty():
                approved_transitions.append(transition)
            elif best_blockers is None or not blockers.has(TransitionBlocker.BLOCKED_BY_MARKING):
                # As in build_transition_blocker_list: a guard's reason beats the marking's.
                best_blockers = blockers

        if not approved_transitions:
            if best_blockers is None:
                raise UndefinedTransitionError(subject, transition_name, self, call_context)
            raise NotEnabledTransitionError(
                subject, transition_name, self, best_blockers, call_context
            )

        for transition in approved_transitions:
            await self._leave(subject, transition, marking, call_context)
            call_context = await self._transition(subject, transition, marking, call_context)
            await self._enter(subject, transition, marking, call_context)
            await self._marking_store.set_marking(subject, marking, call_context)
            await self._entered(subject, transition, marking, call_context)
            await self._completed(subject, transition, marking, call_context)
            await self._announce(subject, transition, marking, call_context)

        marking.set_context(call_context)

        return marking

    @override
    async def get_enabled_transitions(self, subject: object) -> list[Transition]:
        marking = await self.get_marking(subject)

        return [
            transition
            for transition in self._definition.get_transitions()
            if (
                await self._build_transition_blocker_list_for(subject, marking, transition)
            ).is_empty()
        ]

    @override
    async def get_enabled_transition(self, subject: object, name: str) -> Transition | None:
        marking = await self.get_marking(subject)

        for transition in self._transitions_named(name):
            blockers = await self._build_transition_blocker_list_for(subject, marking, transition)
            if blockers.is_empty():
                return transition

        return None

    @override
    def get_name(self) -> str:
        return self._name

    @override
    def get_definition(self) -> Definition:
        return self._definition

    @override
    def get_marking_store(self) -> MarkingStoreInterface:
        return self._marking_store

    @override
    def get_metadata_store(self) -> MetadataStoreInterface:
        return self._definition.get_metadata_store()

    def _transitions_named(self, name: str) -> list[Transition]:
        """Return the transitions named ``name``, in the order the definition gives them."""
        return [t for t in self._definition.get_transitions() if t.get_name() == name]

    async def _build_transition_blocker_list_for(
        self, subject: object, marking: Marking, transition: Transition
    ) -> TransitionBlockerList:
        """Return what blocks ``transition``: the marking first, then the guard listeners.

        The guards are only asked about a transition the marking enables, so
        a listener never weighs a move that could not happen anyway.
        """
        for arc in transition.get_froms(as_arc=True):
            if marking.get_token_count(arc.place) < arc.weight:
                return TransitionBlockerList([TransitionBlocker.create_blocked_by_marking(marking)])

        if self._dispatcher is None:
            return TransitionBlockerList()

        event = GuardEvent(subject, marking, transition, self)
        await self._dispatch_under(
            self._dispatcher, event, WorkflowEvents.GUARD, [transition.get_name()]
        )

        return (
            event.get_transition_blocker_list() if event.is_blocked() else TransitionBlockerList()
        )

    async def _leave(
        self, subject: object, transition: Transition, marking: Marking, context: dict[str, object]
    ) -> None:
        arcs = transition.get_froms(as_arc=True)

        dispatcher = self._dispatcher_for(WorkflowEvents.LEAVE, context)
        if dispatcher is not None:
            event = LeaveEvent(subject, marking, transition, self, context)
            await self._dispatch_under(
                dispatcher, event, WorkflowEvents.LEAVE, [arc.place for arc in arcs]
            )

        for arc in arcs:
            marking.unmark(arc.place, arc.weight)

    async def _transition(
        self, subject: object, transition: Transition, marking: Marking, context: dict[str, object]
    ) -> dict[str, object]:
        """Dispatch ``transition`` and return the context the rest of the move runs with."""
        dispatcher = self._dispatcher_for(WorkflowEvents.TRANSITION, context)
        if dispatcher is None:
            return context

        event = TransitionEvent(subject, marking, transition, self, context)
        await self._dispatch_under(
            dispatcher, event, WorkflowEvents.TRANSITION, [transition.get_name()]
        )

        return event.get_context()

    async def _enter(
        self, subject: object, transition: Transition, marking: Marking, context: dict[str, object]
    ) -> None:
        arcs = transition.get_tos(as_arc=True)

        dispatcher = self._dispatcher_for(WorkflowEvents.ENTER, context)
        if dispatcher is not None:
            event = EnterEvent(subject, marking, transition, self, context)
            await self._dispatch_under(
                dispatcher, event, WorkflowEvents.ENTER, [arc.place for arc in arcs]
            )

        for arc in arcs:
            marking.mark(arc.place, arc.weight)

    async def _entered(
        self,
        subject: object,
        transition: Transition | None,
        marking: Marking,
        context: Mapping[str, object],
    ) -> None:
        """Dispatch ``entered`` for the places ``transition`` entered, or the initial places."""
        dispatcher = self._dispatcher_for(WorkflowEvents.ENTERED, context)
        if dispatcher is None:
            return

        event = EnteredEvent(subject, marking, transition, self, context)
        places = (
            self._definition.get_initial_places() if transition is None else transition.get_tos()
        )
        await self._dispatch_under(dispatcher, event, WorkflowEvents.ENTERED, places)

    async def _completed(
        self, subject: object, transition: Transition, marking: Marking, context: dict[str, object]
    ) -> None:
        dispatcher = self._dispatcher_for(WorkflowEvents.COMPLETED, context)
        if dispatcher is None:
            return

        event = CompletedEvent(subject, marking, transition, self, context)
        await self._dispatch_under(
            dispatcher, event, WorkflowEvents.COMPLETED, [transition.get_name()]
        )

    async def _announce(
        self,
        subject: object,
        initial_transition: Transition,
        marking: Marking,
        context: dict[str, object],
    ) -> None:
        """Dispatch ``announce`` for every transition enabled after the move, guards asked."""
        dispatcher = self._dispatcher_for(WorkflowEvents.ANNOUNCE, context)
        if dispatcher is None:
            return

        event = AnnounceEvent(subject, marking, initial_transition, self, context)
        await self._dispatch_under(dispatcher, event, WorkflowEvents.ANNOUNCE, [])
        # Every guard runs again here, before the first narrowed announce goes out.
        for transition in await self.get_enabled_transitions(subject):
            _ = await dispatcher.dispatch(
                event, f"workflow.{self._name}.announce.{transition.get_name()}"
            )

    async def _dispatch_under(
        self,
        dispatcher: EventDispatcherInterface,
        event: Event,
        event_name: str,
        nodes: Iterable[str],
    ) -> None:
        """Dispatch ``event`` under ``event_name``, narrowed to this workflow, then to each node."""
        _ = await dispatcher.dispatch(event, event_name)
        narrowed = f"workflow.{self._name}.{event_name.removeprefix('workflow.')}"
        _ = await dispatcher.dispatch(event, narrowed)
        for node in nodes:
            _ = await dispatcher.dispatch(event, f"{narrowed}.{node}")

    def _dispatcher_for(
        self, event_name: str, context: Mapping[str, object]
    ) -> EventDispatcherInterface | None:
        """Return the dispatcher, unless ``event_name`` is not to go out for this call."""
        if self._dispatcher is None or context.get(self._DISABLE_EVENTS_MAPPING[event_name]):
            return None
        if self._events_to_dispatch is not None and event_name not in self._events_to_dispatch:
            return None
        return self._dispatcher
