"""A class decorated as a workflow carries what declares it, and nothing it would contradict."""

from __future__ import annotations

import pytest

from tests.fixtures.article_workflow import ArticleWorkflow
from tests.fixtures.place_enum import PlaceEnum
from tests.fixtures.task import Task
from tests.fixtures.task_step import TaskStep
from tests.fixtures.task_workflow import TaskWorkflow
from xtr_workflow import WorkflowType
from xtr_workflow.decorator import AsWorkflow, Place, as_workflow
from xtr_workflow.decorator.as_workflow import workflow_declared_on
from xtr_workflow.exception import LogicError


def test_the_supports_and_support_strategy_arguments_cannot_be_used_together() -> None:
    with pytest.raises(LogicError) as raised:
        _ = AsWorkflow(supports=object, support_strategy="app.support_strategy")

    assert str(raised.value) == (
        'The "supports" and "support_strategy" arguments of "@as_workflow" cannot be used together.'
    )


def test_the_marking_property_and_marking_store_arguments_cannot_be_used_together() -> None:
    with pytest.raises(LogicError) as raised:
        _ = AsWorkflow(marking_property="status", marking_store="app.marking_store")

    assert str(raised.value) == (
        'The "marking_property" and "marking_store" arguments of "@as_workflow" cannot be used '
        "together."
    )


def test_the_description_is_stored_in_the_metadata() -> None:
    declaration = AsWorkflow(description="Manages the articles", metadata={"title": "Articles"})

    assert declaration.metadata == {"title": "Articles", "description": "Manages the articles"}
    assert AsWorkflow(metadata={"title": "Articles"}).metadata == {"title": "Articles"}


def test_the_description_and_a_description_in_the_metadata_cannot_be_used_together() -> None:
    with pytest.raises(LogicError) as raised:
        _ = AsWorkflow(
            description="Manages the articles", metadata={"description": "Manages the posts"}
        )

    assert str(raised.value) == (
        'The "description" argument of "@as_workflow" cannot be used together with a '
        '"description" key in its "metadata" argument.'
    )


def test_a_declaration_without_arguments_declares_a_state_machine_with_defaults() -> None:
    declaration = AsWorkflow()

    assert declaration.name is None
    assert declaration.type is WorkflowType.STATE_MACHINE
    assert declaration.supports == ()
    assert declaration.metadata == {}
    assert not declaration.audit_trail
    assert declaration.events_to_dispatch is None
    assert declaration.place_markers == {}


def test_the_decorator_records_its_declaration_on_the_class() -> None:
    declaration = workflow_declared_on(TaskWorkflow)

    assert declaration is not None
    assert declaration.supports is Task
    assert declaration.marking_property == "step"
    assert declaration.metadata == {"title": "Task"}
    assert declaration.place_markers == {
        TaskStep.NEW: Place(metadata={"label": "New"}),
        TaskStep.PROCESSING: Place(metadata={"label": "Processing", "bg_color": "#eee"}),
    }


def test_the_decorator_returns_the_class_it_decorates() -> None:
    class Article: ...

    assert as_workflow()(Article) is Article


def test_a_subclass_of_a_workflow_class_is_not_a_workflow() -> None:
    class DraftArticleWorkflow(ArticleWorkflow): ...

    assert workflow_declared_on(ArticleWorkflow) is not None
    assert workflow_declared_on(DraftArticleWorkflow) is None


def test_an_undecorated_class_declares_no_workflow() -> None:
    assert workflow_declared_on(Task) is None


def test_a_class_cannot_be_decorated_twice() -> None:
    class Article: ...

    decorated = as_workflow()(Article)

    with pytest.raises(LogicError) as raised:
        _ = as_workflow(name="other")(decorated)

    assert str(raised.value) == (
        f'"{__name__}.{Article.__qualname__}" cannot have several "@as_workflow" decorators.'
    )


def test_an_empty_name_is_refused_when_decorating() -> None:
    class Article: ...

    with pytest.raises(LogicError) as raised:
        _ = as_workflow(name="")(Article)

    assert str(raised.value) == (
        f'The name of the workflow defined by "{__name__}.{Article.__qualname__}" cannot be empty.'
    )


def test_a_place_marker_must_mark_a_case_of_the_places_enum() -> None:
    class Article: ...

    decorate = as_workflow(places=TaskStep, place_markers={PlaceEnum.FOO: Place()})

    with pytest.raises(LogicError) as raised:
        _ = decorate(Article)

    assert str(raised.value) == (
        f'The place "foo" of the workflow defined by "{__name__}.{Article.__qualname__}" is not '
        'a case of "tests.fixtures.task_step.TaskStep".'
    )
    assert workflow_declared_on(Article) is None


def test_a_place_marker_on_a_case_of_the_places_enum_is_kept() -> None:
    class Article: ...

    _ = as_workflow(places=TaskStep, place_markers={TaskStep.DONE: Place(initial=True)})(Article)

    declaration = workflow_declared_on(Article)
    assert declaration is not None
    assert declaration.places is TaskStep
    assert declaration.place_markers == {TaskStep.DONE: Place(initial=True)}
