"""Recording what a workflow is asked, how long it takes to answer, and what it answers."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final, TypeVar, final

from typing_extensions import override
from xtr_clock import MonotonicClock
from xtr_service_contracts import ResetInterface

from xtr_workflow.workflow_interface import WorkflowInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from xtr_clock import ClockInterface

    from xtr_workflow.definition import Definition
    from xtr_workflow.marking import Marking
    from xtr_workflow.marking_store import MarkingStoreInterface
    from xtr_workflow.metadata import MetadataStoreInterface
    from xtr_workflow.transition import Transition
    from xtr_workflow.transition_blocker_list import TransitionBlockerList

__all__ = ["TraceableWorkflow"]

_T = TypeVar("_T")

_MILLISECOND: Final = timedelta(milliseconds=1)


@final
class TraceableWorkflow(WorkflowInterface, ResetInterface):
    """Wraps a workflow and records every call that may ask its listeners.

    Debugging a workflow starts with what it was asked: which transitions
    were tried and applied, where the subject was before, how long each call
    took, what came back and what went wrong. Every call of
    :meth:`get_marking`, :meth:`can`, :meth:`build_transition_blocker_list`,
    :meth:`apply`, :meth:`get_enabled_transitions` and
    :meth:`get_enabled_transition` adds a record to :meth:`get_calls`, under
    these keys:

    * ``method``: the name of the method called;
    * ``duration``: how long it took, in milliseconds;
    * ``args``: every argument it took, in order, defaults included;
    * ``previous_marking``: for ``apply``, the marking the subject was in
      before it moved, read from the wrapped workflow first; ``None`` when
      that read fails, and for every other method;
    * ``return``: what it returned — or ``exception``: what it raised, which
      is raised on once recorded.

    The name, the definition and the stores only read the wrapped workflow,
    and are answered unrecorded.

    The records grow with every call until :meth:`reset`, which a
    long-running process calls between units of work. While ``disabled``
    answers true, a call goes straight to the wrapped workflow, unrecorded.
    """

    __slots__: tuple[str, ...] = ("_calls", "_clock", "_disabled", "_workflow")

    _workflow: WorkflowInterface
    _clock: ClockInterface
    _disabled: Callable[[], bool] | None
    _calls: list[dict[str, object]]

    def __init__(
        self,
        workflow: WorkflowInterface,
        clock: ClockInterface | None = None,
        disabled: Callable[[], bool] | None = None,
    ) -> None:
        """Record the calls made to ``workflow``.

        Args:
            workflow: The workflow every call is handed to.
            clock: What each call is timed against; a monotonic clock when
                ``None``, so a correction of the wall clock never makes a call
                look shorter or longer than it was.
            disabled: Asked before each call whether to leave it unrecorded;
                ``None`` records every call.
        """
        self._workflow = workflow
        self._clock = clock if clock is not None else MonotonicClock()
        self._disabled = disabled
        self._calls = []

    @override
    async def get_marking(
        self, subject: object, context: Mapping[str, object] | None = None
    ) -> Marking:
        return await self._call_inner(
            "get_marking",
            (subject, context),
            lambda: self._workflow.get_marking(subject, context),
        )

    @override
    async def can(self, subject: object, transition_name: str) -> bool:
        return await self._call_inner(
            "can",
            (subject, transition_name),
            lambda: self._workflow.can(subject, transition_name),
        )

    @override
    async def build_transition_blocker_list(
        self, subject: object, transition_name: str
    ) -> TransitionBlockerList:
        return await self._call_inner(
            "build_transition_blocker_list",
            (subject, transition_name),
            lambda: self._workflow.build_transition_blocker_list(subject, transition_name),
        )

    @override
    async def apply(
        self,
        subject: object,
        transition_name: str,
        context: Mapping[str, object] | None = None,
    ) -> Marking:
        return await self._call_inner(
            "apply",
            (subject, transition_name, context),
            lambda: self._workflow.apply(subject, transition_name, context),
        )

    @override
    async def get_enabled_transitions(self, subject: object) -> list[Transition]:
        return await self._call_inner(
            "get_enabled_transitions",
            (subject,),
            lambda: self._workflow.get_enabled_transitions(subject),
        )

    @override
    async def get_enabled_transition(self, subject: object, name: str) -> Transition | None:
        return await self._call_inner(
            "get_enabled_transition",
            (subject, name),
            lambda: self._workflow.get_enabled_transition(subject, name),
        )

    @override
    def get_name(self) -> str:
        return self._workflow.get_name()

    @override
    def get_definition(self) -> Definition:
        return self._workflow.get_definition()

    @override
    def get_marking_store(self) -> MarkingStoreInterface:
        return self._workflow.get_marking_store()

    @override
    def get_metadata_store(self) -> MetadataStoreInterface:
        return self._workflow.get_metadata_store()

    def get_calls(self) -> list[dict[str, object]]:
        """Return the record of every call made since the last reset, in the order they finished.

        A list of its own: holding on to it does not hold on to the one this
        workflow goes on adding to.
        """
        return list(self._calls)

    def get_inner(self) -> WorkflowInterface:
        """Return the workflow every call is handed to.

        For code that needs the workflow itself — its class, say, which tells a
        state machine from a workflow — rather than this record of it.
        """
        return self._workflow

    @override
    async def reset(self) -> None:
        """Forget every call recorded, so the next unit of work starts with none."""
        self._calls.clear()

    async def _call_inner(
        self, method: str, arguments: tuple[object, ...], call: Callable[[], Awaitable[_T]]
    ) -> _T:
        """Make ``call`` to the wrapped workflow, recorded as ``method`` called with ``arguments``.

        The clock is read first, so reading the marking a subject is in
        before ``apply`` counts in that call's duration.
        """
        if self._disabled is not None and self._disabled():
            return await call()

        started = self._clock.now()
        previous_marking = await self._marking_before(arguments[0]) if method == "apply" else None

        def record(outcome: str, value: object) -> None:
            self._calls.append(
                {
                    "method": method,
                    "duration": (self._clock.now() - started) / _MILLISECOND,
                    "args": arguments,
                    "previous_marking": previous_marking,
                    outcome: value,
                }
            )

        try:
            returned = await call()
        except Exception as error:
            record("exception", error)
            raise

        record("return", returned)
        return returned

    async def _marking_before(self, subject: object) -> Marking | None:
        """Return the marking ``subject`` is in before it moves; ``None`` when it cannot be read.

        Only the record needs it, so a marking that cannot be read stops
        nothing here: the move itself raises whatever stops it.
        """
        try:
            return await self._workflow.get_marking(subject)
        except Exception:  # noqa: BLE001 -- only the record needs it; the move raises on its own
            return None
