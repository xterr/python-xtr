"""The workflow declared on a class."""

from __future__ import annotations

from typing import Annotated, ClassVar, final

from xtr_workflow.decorator import Transition, as_workflow


@final
@as_workflow(supports=object)
class TaskWorkflow:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"
