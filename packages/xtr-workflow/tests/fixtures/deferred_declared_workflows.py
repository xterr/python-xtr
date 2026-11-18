"""Workflows declared with deferred annotations, some naming what only the type checker imports.

The one module here that does not import ``annotations`` from ``__future__``:
the annotations of its classes are evaluated only when read, all at once.
"""

from typing import TYPE_CHECKING, Annotated, ClassVar

from xtr_workflow import WorkflowTrait
from xtr_workflow.decorator import Transition, as_workflow

if TYPE_CHECKING:
    from tests.fixtures.task import Task
    from tests.fixtures.task_step import TaskStep


@as_workflow(supports=object)
class DeferredTaskQueueWorkflow(WorkflowTrait):
    _current: Task | None = None
    # A lambda cannot be written back as source, as every other value here can.
    QUEUE: ClassVar[
        Annotated[str, Transition(froms="new", tos="queued", guard=lambda _context: True)]
    ] = "queue"


@as_workflow(supports=object)
class DeferredTaskStepWorkflow:
    # The marker needs ``TaskStep`` at runtime, which only the type checker imports.
    GO: ClassVar[Annotated[str, Transition(froms=TaskStep.NEW, tos="b")]] = "go"
