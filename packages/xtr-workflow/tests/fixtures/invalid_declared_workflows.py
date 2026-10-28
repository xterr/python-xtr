"""Workflows declared on classes that no configuration can be read from, each for its own reason."""

from __future__ import annotations

from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Annotated, ClassVar, Final, cast

from tests.fixtures.declared_workflows import Step
from xtr_workflow.decorator import Place, Transition, as_workflow

if TYPE_CHECKING:
    from tests.fixtures.task_step import TaskStep

# What a declaration typed loosely could still hand over as a place.
NOT_A_PLACE: Final = cast("str", cast("object", 1))


class IntStep(IntEnum):
    ONE = 1


@as_workflow(supports=object)
class IntConstantWorkflow:
    GO: ClassVar[Annotated[int, Transition(froms="a", tos="b")]] = 1


@as_workflow(supports=object)
class InvalidArcWorkflow:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos=[NOT_A_PLACE])]] = "go"


@as_workflow(supports=object)
class IntEnumWorkflow:
    GO: ClassVar[Annotated[str, Transition(froms=IntStep.ONE, tos="b")]] = "go"


@as_workflow(supports=object)
class JoinStateMachine:
    GO: ClassVar[Annotated[str, Transition(froms=("a", "b"), tos="c")]] = "go"


@as_workflow(supports=object)
class SplitStateMachine:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos=("b", "c"))]] = "go"


@as_workflow(supports=object)
class DuplicatePlaceWorkflow:
    A: ClassVar[Annotated[str, Place()]] = "a"
    B: ClassVar[Annotated[str, Place()]] = "a"
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"


@as_workflow(supports=object)
class IntPlaceConstantWorkflow:
    ONE: ClassVar[Annotated[int, Place()]] = 1
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"


@as_workflow(supports=object, places=cast("type[Enum]", object))
class PlacesFromClassWorkflow:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"


@as_workflow(supports=object, places=Step)
class PlaceNotInEnumWorkflow:
    GO: ClassVar[Annotated[str, Transition(froms=Step.NEW, tos="foreign")]] = "go"


@as_workflow(supports=object)
class SeveralPlaceMarkersWorkflow:
    START: ClassVar[Annotated[str, Place(initial=True), Place(metadata={"label": "Start"})]] = (
        "start"
    )
    GO: ClassVar[Annotated[str, Transition(froms=START, tos="end")]] = "go"


@as_workflow(supports=object)
class NoTransitionWorkflow:
    DRAFT: ClassVar[Annotated[str, Place()]] = "draft"


@as_workflow(supports=object)
class TypeCheckingStepWorkflow:
    # Only the type checker imports ``TaskStep``, which the marker needs at runtime.
    GO: ClassVar[Annotated[str, Transition(froms=TaskStep.NEW, tos="b")]] = "go"
