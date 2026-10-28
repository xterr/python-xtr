"""A workflow whose subject is in exactly one place at a time."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .marking_store import MethodMarkingStore
from .workflow import Workflow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface

    from .definition import Definition
    from .marking_store import MarkingStoreInterface

__all__ = ["StateMachine"]


@final
class StateMachine(Workflow):
    """A workflow whose subject is in exactly one place at a time.

    It moves subjects as a workflow does; what differs is where it keeps
    them: unless given a store, the subject keeps the name of its one place
    rather than a dict of places. Several transitions may share a name — one
    for each place it leaves — and applying the name applies the one the
    subject's place enables.
    """

    __slots__: tuple[str, ...] = ()

    def __init__(
        self,
        definition: Definition,
        marking_store: MarkingStoreInterface | None = None,
        dispatcher: EventDispatcherInterface | None = None,
        name: str = "unnamed",
        events_to_dispatch: Sequence[str] | None = None,
    ) -> None:
        """Move subjects through ``definition``, each keeping the name of its place.

        Args:
            definition: The places and transitions.
            marking_store: Where each subject's marking is kept; on the subject,
                as the name of its place, when ``None``.
            dispatcher: Where the events go; none is dispatched without one.
            name: The name of the state machine, narrowing the events' names.
            events_to_dispatch: Which events go out besides the guard, as
                :class:`~xtr_workflow.workflow.Workflow` reads it.

        Raises:
            InvalidArgumentError: If ``events_to_dispatch`` mixes listed and
                ``!``-prefixed entries, or blocks the guard.
        """
        super().__init__(
            definition,
            MethodMarkingStore(single_state=True) if marking_store is None else marking_store,
            dispatcher,
            name,
            events_to_dispatch,
        )
