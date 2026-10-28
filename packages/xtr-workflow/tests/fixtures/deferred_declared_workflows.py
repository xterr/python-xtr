"""Workflows declared with deferred annotations, some naming what only the type checker imports.

The one module here that does not import ``annotations`` from ``__future__``:
from 3.14 on, the annotations of its classes are evaluated only when read, all
at once. Before 3.14 they are evaluated as each class is created, which fails
on the first naming what only the type checker imports — so it is imported from
3.14 on only.
"""

from typing import TYPE_CHECKING, Annotated, ClassVar

from xtr_workflow import WorkflowTrait
from xtr_workflow.decorator import Transition, as_workflow

if TYPE_CHECKING:
    from tests.fixtures.task import Task  # noqa: TC004 — deferred, not needed to create a class
    from tests.fixtures.task_step import TaskStep  # noqa: TC004 — a marker lacking it is the point


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
