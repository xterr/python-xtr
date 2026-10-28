"""A state machine moving tasks, declared on a class it answers for, and a second one beside it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, ClassVar, final

from xtr_dependency_injection import Target, as_service

from tests.fixtures.task import Task
from tests.fixtures.task_step import TaskStep
from xtr_workflow import WorkflowInterface, WorkflowTrait
from xtr_workflow.decorator import (
    Place,
    Transition,
    as_guard_listener,
    as_transition_listener,
    as_workflow,
)
from xtr_workflow.event import GuardEvent, TransitionEvent

if TYPE_CHECKING:
    from xtr_workflow import Marking


@final
@as_workflow(
    supports=Task,
    marking_property="step",
    metadata={"title": "Task"},
    place_markers={
        TaskStep.NEW: Place(metadata={"label": "New"}),
        TaskStep.PROCESSING: Place(metadata={"label": "Processing", "bg_color": "#eee"}),
    },
)
class TaskWorkflow(WorkflowTrait):
    # Only the type checker imports ``Marking``: the bundle reads the markers past it.
    _last_marking: Marking | None = None
    START: ClassVar[Annotated[str, Transition(froms=TaskStep.NEW, tos=TaskStep.PROCESSING)]] = (
        "start"
    )
    FINISH: ClassVar[
        Annotated[
            str,
            Transition(froms=TaskStep.PROCESSING, tos=TaskStep.DONE),
            Transition(froms=TaskStep.FAILED, tos=TaskStep.DONE),
        ]
    ] = "finish"
    FAIL: ClassVar[Annotated[str, Transition(froms=TaskStep.PROCESSING, tos=TaskStep.FAILED)]] = (
        "fail"
    )

    async def start(self, task: Task) -> Marking:
        return await self.apply(task, self.START, {"started_by": "start()"})

    @as_guard_listener(transition=START)
    def guard_start(self, event: GuardEvent) -> None:
        subject = event.get_subject()
        if isinstance(subject, Task) and subject.blocked:
            event.set_blocked(True, "The task is blocked.")

    @as_transition_listener(transition=START)
    def on_start(self, event: TransitionEvent) -> None:
        subject = event.get_subject()
        if isinstance(subject, Task):
            subject.context = event.get_context()


@final
class Chore:
    """Moved by the second state machine, which has a ``start`` transition too."""

    def __init__(self) -> None:
        self.marking: object = None
        self.blocked = True


@final
@as_workflow(supports=Chore)
class ChoreStateMachine:
    START: ClassVar[Annotated[str, Transition(froms="new", tos="processing")]] = "start"


@final
@as_service
class TaskConsumer:
    def __init__(
        self,
        task_workflow: TaskWorkflow,
        workflow: Annotated[WorkflowInterface, Target("task")],
    ) -> None:
        self.task_workflow = task_workflow
        self.workflow = workflow
