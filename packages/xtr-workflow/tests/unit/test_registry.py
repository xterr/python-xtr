"""A registry finds the workflows supporting a subject, among those added to it."""

from __future__ import annotations

from typing import final

import pytest

from xtr_workflow import Definition, Registry, Workflow
from xtr_workflow.exception import InvalidArgumentError
from xtr_workflow.support_strategy import InstanceOfSupportStrategy


@final
class Subject1:
    """A subject only the first workflow supports."""


@final
class Subject2:
    """A subject the second and the third workflows both support."""


@pytest.fixture
def registry() -> Registry:
    registry = Registry()
    registry.add_workflow(
        Workflow(Definition([], []), name="workflow1"), InstanceOfSupportStrategy(Subject1)
    )
    registry.add_workflow(
        Workflow(Definition([], []), name="workflow2"), InstanceOfSupportStrategy(Subject2)
    )
    registry.add_workflow(
        Workflow(Definition([], []), name="workflow3"), InstanceOfSupportStrategy(Subject2)
    )
    return registry


def test_it_has_a_workflow_supporting_the_subject(registry: Registry) -> None:
    assert registry.has(Subject1())


def test_it_has_no_workflow_of_another_name_supporting_the_subject(registry: Registry) -> None:
    assert not registry.has(Subject1(), "nope")


@pytest.mark.parametrize(
    ("subject", "workflow_name", "expected"),
    [
        pytest.param(Subject1(), None, "workflow1", id="the-only-one-supporting-it"),
        pytest.param(Subject1(), "workflow1", "workflow1", id="the-only-one-supporting-it-named"),
        pytest.param(Subject2(), "workflow2", "workflow2", id="the-one-named-among-several"),
    ],
)
def test_it_gets_the_one_workflow_supporting_the_subject(
    registry: Registry, subject: object, workflow_name: str | None, expected: str
) -> None:
    workflow = registry.get(subject, workflow_name)

    assert workflow.get_name() == expected


def test_getting_the_workflow_of_a_subject_several_support_is_refused(
    registry: Registry,
) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = registry.get(Subject2())

    assert str(raised.value) == (
        "Too many workflows (workflow2, workflow3) match this subject (Subject2); set a "
        "different name on each and use the second (name) argument of this method."
    )


def test_getting_the_workflow_of_a_subject_none_supports_is_refused(registry: Registry) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = registry.get(object())

    assert str(raised.value) == 'Unable to find a workflow for class "object".'


def test_all_returns_the_one_workflow_supporting_the_subject(registry: Registry) -> None:
    workflows = registry.all(Subject1())

    assert [workflow.get_name() for workflow in workflows] == ["workflow1"]


def test_all_returns_every_workflow_supporting_the_subject_in_the_order_they_were_added(
    registry: Registry,
) -> None:
    workflows = registry.all(Subject2())

    assert [workflow.get_name() for workflow in workflows] == ["workflow2", "workflow3"]


def test_all_returns_no_workflow_for_a_subject_none_supports(registry: Registry) -> None:
    assert registry.all(object()) == []
