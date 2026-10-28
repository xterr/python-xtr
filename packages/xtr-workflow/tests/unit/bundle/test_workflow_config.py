"""The bundle's configuration holds every workflow by name, and none by default."""

from __future__ import annotations

from typing import cast

import pytest

from xtr_workflow import WorkflowType
from xtr_workflow.bundle import TransitionConfig, WorkflowConfig, WorkflowDefinitionConfig
from xtr_workflow.exception import InvalidArgumentError

_BLOG = WorkflowDefinitionConfig(
    supports=(object,), places=("a", "b"), transitions=(TransitionConfig("go", "a", "b"),)
)


def test_no_workflow_is_configured_by_default() -> None:
    assert WorkflowConfig().workflows == {}


def test_workflows_are_kept_by_name_in_the_order_given() -> None:
    config = WorkflowConfig(workflows={"blog": _BLOG, "news": _BLOG})

    assert list(config.workflows) == ["blog", "news"]


def test_a_workflow_named_workflows_can_set_any_option() -> None:
    config = WorkflowConfig(
        workflows={
            "workflows": WorkflowDefinitionConfig(
                type=WorkflowType.WORKFLOW,
                supports=(object,),
                places=("draft", "published"),
                transitions=(TransitionConfig("publish", "draft", "published"),),
                events_to_dispatch=(),
                metadata={"title": "Workflows"},
            )
        }
    )

    assert list(config.workflows) == ["workflows"]
    assert config.workflows["workflows"].metadata == {"title": "Workflows"}


def test_a_workflow_must_be_a_workflow_configuration() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowConfig(
            workflows={"blog": cast("WorkflowDefinitionConfig", cast("object", "foo"))}
        )

    assert str(raised.value) == (
        'Invalid type for path "workflow.workflows.blog". Expected "WorkflowDefinitionConfig", '
        'but got "str".'
    )
