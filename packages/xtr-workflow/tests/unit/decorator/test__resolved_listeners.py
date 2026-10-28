"""A workflow class's listeners that name no workflow listen to the class's own."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast, get_type_hints

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_event_dispatcher.decorator import (
    EventListenerDeclaration,
    as_event_listener,
    listeners_declared_on,
)
from xtr_event_dispatcher.decorator.event_listener_declaration import recorded_on

from tests.fixtures.article_workflow import ArticleWorkflow
from tests.fixtures.pull_request_state_machine import PullRequestStateMachine
from tests.fixtures.review_listeners import ReviewListeners
from tests.fixtures.scoped_listeners_workflow import ScopedListenersWorkflow
from tests.fixtures.subject import Subject
from tests.fixtures.task import Task
from tests.fixtures.task_step import TaskStep
from tests.fixtures.task_workflow import TaskWorkflow
from xtr_workflow import Definition, Marking, StateMachine, Transition, Workflow
from xtr_workflow.decorator import as_guard_listener, as_workflow
from xtr_workflow.event import AnnounceEvent, GuardEvent, LeaveEvent
from xtr_workflow.marking_store import MethodMarkingStore

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio

_OVERRIDDEN = ("guard_approve", "on_review", "enter_approved", "announce", "leave_draft")


def _review_listeners(name: str) -> tuple[EventListenerDeclaration, ...]:
    return (
        EventListenerDeclaration(f"workflow.{name}.guard.approve", "guard_approve", 5),
        EventListenerDeclaration(f"workflow.{name}.entered.approved", "on_review"),
        EventListenerDeclaration(f"workflow.{name}.completed", "on_review"),
        EventListenerDeclaration(f"workflow.{name}.enter.approved", "enter_approved"),
        EventListenerDeclaration(f"workflow.{name}.announce.approve", "announce"),
        EventListenerDeclaration(f"workflow.{name}.leave.draft", "leave_draft"),
        EventListenerDeclaration("workflow.other.guard.approve", "guard_other"),
    )


def _listen(dispatcher: EventDispatcher, listener: object) -> None:
    """Register what ``listener``'s class declares, as the event dispatcher bundle would."""
    for declaration in listeners_declared_on(type(listener)):
        assert isinstance(declaration.event, str)
        assert declaration.method is not None
        method = cast("Callable[..., object]", getattr(listener, declaration.method))
        dispatcher.add_listener(declaration.event, method, declaration.priority or 0)


def _review_workflow(dispatcher: EventDispatcher, name: str) -> Workflow:
    definition = Definition(["draft", "approved"], [Transition("approve", "draft", "approved")])
    return Workflow(definition, MethodMarkingStore(single_state=True), dispatcher, name)


def test_listeners_without_a_workflow_listen_to_the_workflow_of_the_class() -> None:
    assert listeners_declared_on(ScopedListenersWorkflow) == (
        EventListenerDeclaration("workflow.scoped_listeners.completed", "on_completed"),
        EventListenerDeclaration("workflow.scoped_listeners.guard", "guard_all"),
        EventListenerDeclaration("workflow.scoped_listeners.guard.go", "guard_go"),
        EventListenerDeclaration("workflow.other.guard", "guard_other"),
        EventListenerDeclaration("workflow.guard", "guard_every_workflow"),
    )


def test_a_method_written_in_the_class_is_resolved_in_place() -> None:
    function = cast("object", vars(TaskWorkflow)["guard_start"])

    assert recorded_on(function) == (EventListenerDeclaration("workflow.task.guard.start"),)


@pytest.mark.parametrize(
    ("workflow_class", "name"),
    [(ArticleWorkflow, "article"), (PullRequestStateMachine, "pull_request")],
)
def test_two_workflow_classes_sharing_a_base_each_listen_to_their_own_workflow(
    workflow_class: type[ReviewListeners], name: str
) -> None:
    assert listeners_declared_on(workflow_class) == _review_listeners(name)


def test_the_shared_base_keeps_its_unresolved_listeners() -> None:
    assert listeners_declared_on(ReviewListeners)[:3] == (
        EventListenerDeclaration("workflow.@self.guard.approve", "guard_approve", 5),
        EventListenerDeclaration("workflow.@self.entered.approved", "on_review"),
        EventListenerDeclaration("workflow.completed", "on_review"),
    )


@pytest.mark.parametrize("name", _OVERRIDDEN)
def test_an_inherited_listener_is_overridden_keeping_its_signature(name: str) -> None:
    inherited = cast("Callable[..., object]", getattr(ReviewListeners, name))

    override = cast("Callable[..., object]", getattr(ArticleWorkflow, name))

    assert name in vars(ArticleWorkflow)
    written = cast("object", vars(ArticleWorkflow)[name])
    assert type(written) is type(cast("object", vars(ReviewListeners)[name]))
    assert inspect.signature(override) == inspect.signature(inherited)
    assert get_type_hints(override) == get_type_hints(inherited)
    assert getattr(override, "__qualname__", None) == f"ArticleWorkflow.{name}"


def test_a_scoped_or_plain_inherited_method_is_not_overridden() -> None:
    assert "guard_other" not in vars(ArticleWorkflow)
    assert "describe" not in vars(ArticleWorkflow)


async def test_the_overrides_call_the_inherited_methods() -> None:
    dispatcher = EventDispatcher()
    article = ArticleWorkflow()
    pull_request = PullRequestStateMachine()
    _listen(dispatcher, article)
    _listen(dispatcher, pull_request)
    workflow = _review_workflow(dispatcher, "article")

    _ = await workflow.apply(Subject(), "approve")

    assert article.heard == [
        "guard article",
        "enter article",
        "review article",
        "review article",
    ]
    assert pull_request.heard == []
    assert article.describe() == "ArticleWorkflow"


def test_static_and_class_method_overrides_call_the_inherited_ones() -> None:
    workflow = _review_workflow(EventDispatcher(), "article")
    marking = Marking({"draft": 1})

    announced = ArticleWorkflow.announce(AnnounceEvent(Subject(), marking, None, workflow))
    left = ArticleWorkflow.leave_draft(LeaveEvent(Subject(), marking, None, workflow))

    assert announced == "announce article"
    assert left == "ArticleWorkflow leaves article"


def test_a_workflow_subclass_of_a_workflow_class_listens_to_its_own_workflow() -> None:
    @as_workflow(name="draft")
    class DraftArticleWorkflow(ArticleWorkflow): ...

    assert listeners_declared_on(DraftArticleWorkflow) == _review_listeners("draft")
    assert listeners_declared_on(ArticleWorkflow) == _review_listeners("article")


def test_a_workflow_subclass_resolves_methods_its_base_resolved_in_place() -> None:
    class Base:
        @as_guard_listener(transition="go")
        def guard_go(self) -> None: ...

    decorated_base = as_workflow(name="base")(Base)

    @as_workflow(name="child")
    class Child(decorated_base): ...

    assert listeners_declared_on(Child) == (
        EventListenerDeclaration("workflow.child.guard.go", "guard_go"),
    )
    assert listeners_declared_on(decorated_base) == (
        EventListenerDeclaration("workflow.base.guard.go", "guard_go"),
    )


def test_a_class_that_is_not_a_workflow_keeps_its_placeholder() -> None:
    class Orphan:
        @as_guard_listener(transition="go")
        def guard(self) -> None: ...

    assert listeners_declared_on(Orphan) == (
        EventListenerDeclaration("workflow.@self.guard.go", "guard"),
    )


def test_a_listener_of_an_event_class_or_of_its_annotation_is_left_alone() -> None:
    @as_workflow(name="article")
    class Article:
        @as_event_listener(GuardEvent)
        @as_event_listener()
        def on_guard(self, _event: GuardEvent) -> None: ...

    assert listeners_declared_on(Article) == (
        EventListenerDeclaration(None, "on_guard"),
        EventListenerDeclaration(GuardEvent, "on_guard"),
    )


async def test_a_workflow_class_using_the_trait_hears_its_own_workflow() -> None:
    dispatcher = EventDispatcher()
    task_workflow = TaskWorkflow()
    _listen(dispatcher, task_workflow)
    definition = Definition(
        [step.value for step in TaskStep],
        [
            Transition("start", "new", "processing"),
            Transition("finish", "processing", "done"),
            Transition("finish", "failed", "done"),
            Transition("fail", "processing", "failed"),
        ],
    )
    task_workflow.set_workflow(
        StateMachine(
            definition,
            MethodMarkingStore(single_state=True, marking_property="step"),
            dispatcher,
            "task",
        )
    )
    blocked = Task()
    blocked.blocked = True
    task = Task()

    assert not await task_workflow.can(blocked, TaskWorkflow.START)
    marking = await task_workflow.start(task)

    assert marking.get_places() == {"processing": 1}
    assert task.step is TaskStep.PROCESSING
    assert task.context == {"started_by": "start()"}
