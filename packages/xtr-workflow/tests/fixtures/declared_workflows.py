"""Workflows declared on classes, each showing one way a declaration is read."""

from __future__ import annotations

from collections.abc import Mapping, Sized
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Annotated, ClassVar, Final

from tests.fixtures.definition_validator import DefinitionValidator
from xtr_workflow import Arc, WorkflowTrait, WorkflowType
from xtr_workflow.decorator import Place, Transition, as_workflow
from xtr_workflow.event_listener import GuardContext

if TYPE_CHECKING:
    from tests.fixtures.task import Task


class Step(StrEnum):
    NEW = "new"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    ARCHIVED = "archived"


STEP_MARKERS: Final[Mapping[Enum, Place]] = {
    Step.NEW: Place(metadata={"label": "New"}),
    Step.PROCESSING: Place(metadata={"label": "Processing", "bg_color": "#eee"}),
}


class ArticleStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ArticleStep(StrEnum):
    PUBLISHED = "published"


class ExtendedStep(StrEnum):
    REVIEWED = "reviewed"


def is_user(context: GuardContext) -> bool:
    return "ROLE_USER" in context.role_names


def always(_context: GuardContext) -> bool:
    return True


@as_workflow(supports=object)
class TaskWorkflow:
    START: ClassVar[Annotated[str, Transition(froms="new", tos="processing")]] = "start"
    FINISH: ClassVar[Annotated[str, Transition(froms="processing", tos="done")]] = "finish"


@as_workflow(supports=object)
class OrderV2Workflow:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"


@as_workflow(supports=object)
class HTMLPageWorkflow:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"


@as_workflow(supports=object)
class Reviewing:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"


@as_workflow(name="explicit.name", supports=object)
class NamedWorkflow:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"


@as_workflow(
    name="full",
    type=WorkflowType.WORKFLOW,
    supports=(object, Sized),
    initial_marking=(Step.NEW, "extra"),
    marking_property="step",
    metadata={"title": "Full"},
    audit_trail=True,
    events_to_dispatch=("!workflow.announce",),
    definition_validators=(DefinitionValidator,),
    place_markers=STEP_MARKERS,
)
class FullWorkflow:
    EXTRA: ClassVar[Annotated[str, Place(metadata={"label": "Extra"})]] = "extra"
    ORPHAN: ClassVar[Annotated[str, Place()]] = "orphan"
    START: ClassVar[
        Annotated[
            str,
            Transition(
                froms=Step.NEW, tos=Step.PROCESSING, guard=is_user, metadata={"color": "blue"}
            ),
        ]
    ] = "start"
    FINISH: ClassVar[
        Annotated[
            str,
            Transition(froms=Step.PROCESSING, tos=Step.DONE),
            Transition(froms=Step.FAILED, tos=Step.DONE),
        ]
    ] = "finish"
    MERGE: ClassVar[
        Annotated[
            str,
            Transition(
                froms=(Arc(Step.DONE.value, 2), EXTRA),
                tos=Step.ARCHIVED,
                guard=always,
                metadata={"label": "Merge"},
            ),
        ]
    ] = "merge"


@as_workflow(support_strategy="app.support_strategy", marking_store="app.marking_store")
class ServicesWorkflow:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"


@as_workflow(supports=object, places=Step, place_markers=STEP_MARKERS)
class EnumPlacesWorkflow:
    ARCHIVE: ClassVar[Annotated[str, Transition(froms=Step.DONE, tos=Step.ARCHIVED)]] = "archive"


@as_workflow(supports=object)
class PlaceConstantsWorkflow:
    ARCHIVED: ClassVar[Annotated[str, Place()]] = "archived"
    DRAFT: ClassVar[Annotated[str, Place(metadata={"label": "Draft"})]] = "draft"
    PUBLISH: ClassVar[Annotated[str, Transition(froms=DRAFT, tos="published")]] = "publish"


@as_workflow(
    name="article",
    supports=object,
    description="Manages the articles",
    metadata={"title": "Articles"},
    place_markers={ArticleStep.PUBLISHED: Place("Visible by everyone", {"label": "Published"})},
)
class DescribedArticleWorkflow:
    DRAFT: ClassVar[Annotated[str, Place("Being written", initial=True)]] = "draft"
    PUBLISH: ClassVar[
        Annotated[
            str,
            Transition(
                froms=DRAFT,
                tos=ArticleStep.PUBLISHED,
                description="Makes the article public",
                guard=always,
            ),
        ]
    ] = "publish"
    ARCHIVE: ClassVar[Annotated[str, Transition(froms=ArticleStep.PUBLISHED, tos="archived")]] = (
        "archive"
    )


@as_workflow(supports=object, place_markers={ArticleStatus.DRAFT: Place(initial=True)})
class InitialCaseStateMachine:
    ARCHIVE: ClassVar[
        Annotated[str, Transition(froms=ArticleStatus.PUBLISHED, tos=ArticleStatus.ARCHIVED)]
    ] = "archive"
    PUBLISH: ClassVar[
        Annotated[str, Transition(froms=ArticleStatus.DRAFT, tos=ArticleStatus.PUBLISHED)]
    ] = "publish"


@as_workflow(supports=object)
class InitialConstantStateMachine:
    PENDING: ClassVar[Annotated[str, Place(initial=True)]] = "pending"
    SUBMIT: ClassVar[Annotated[str, Transition(froms="new", tos=PENDING)]] = "submit"


@as_workflow(
    type=WorkflowType.WORKFLOW,
    supports=object,
    place_markers={ArticleStatus.DRAFT: Place(initial=True)},
)
class InitialPlacesWorkflow:
    REVIEW: ClassVar[Annotated[str, Place(initial=True)]] = "review"
    PUBLISH: ClassVar[
        Annotated[str, Transition(froms=(ArticleStatus.DRAFT, REVIEW), tos=ArticleStatus.PUBLISHED)]
    ] = "publish"


@as_workflow(
    supports=object,
    initial_marking=ArticleStatus.PUBLISHED,
    place_markers={ArticleStatus.DRAFT: Place(initial=True)},
)
class ExplicitInitialMarkingStateMachine:
    PUBLISH: ClassVar[
        Annotated[str, Transition(froms=ArticleStatus.DRAFT, tos=ArticleStatus.PUBLISHED)]
    ] = "publish"


@as_workflow(supports=object, place_markers={ArticleStatus.DRAFT: Place(initial=True)})
class UnusedInitialCaseStateMachine:
    ARCHIVE: ClassVar[
        Annotated[str, Transition(froms=ArticleStatus.PUBLISHED, tos=ArticleStatus.ARCHIVED)]
    ] = "archive"


@as_workflow(
    supports=object,
    place_markers={ExtendedStep.REVIEWED: Place(metadata={"label": "Reviewed"}, initial=True)},
)
class MarkedPlacesWorkflow:
    DRAFT: ClassVar[Annotated[str, Place(metadata={"label": "Draft", "bg_color": "#eee"})]] = (
        "draft"
    )
    PUBLISH: ClassVar[
        Annotated[
            str,
            Transition(froms=DRAFT, tos="published", metadata={"label": "Publish", "async": True}),
            Transition(froms=ExtendedStep.REVIEWED, tos="published", metadata={"async": False}),
        ]
    ] = "publish"


class TransitionsBase:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"


@as_workflow(supports=object)
class InheritedTransitionsWorkflow(TransitionsBase):
    BACK: ClassVar[Annotated[str, Transition(froms="b", tos="a")]] = "back"


@as_workflow(supports=object)
class OverridingTransitionsWorkflow(TransitionsBase):
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="c")]] = "go"
    title: str = "Not a marked constant"


@as_workflow(supports=object)
class TaskQueueWorkflow(WorkflowTrait):
    # Only the type checker imports ``Task``: this annotation cannot be read at runtime.
    _current: Task | None = None
    QUEUE: ClassVar[Annotated[str, Transition(froms="new", tos="queued")]] = "queue"
