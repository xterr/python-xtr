"""A state machine declared on a class, moving tasks, with listeners of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, ClassVar, final

from tests.fixtures.task import Task
from tests.fixtures.task_step import TaskStep
from xtr_workflow.decorator import (
    Place,
    Transition,
    as_guard_listener,
    as_transition_listener,
    as_workflow,
)
from xtr_workflow.event import GuardEvent, TransitionEvent
from xtr_workflow.workflow_trait import WorkflowTrait

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
