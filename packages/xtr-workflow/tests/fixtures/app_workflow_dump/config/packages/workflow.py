"""A workflow whose publication needs an editor, and a state machine moving pull requests."""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.fixtures.app_workflow_dump.guards import is_editor
from xtr_workflow import WorkflowType
from xtr_workflow.bundle import TransitionConfig, WorkflowConfig, WorkflowDefinitionConfig


@configure
def workflow() -> WorkflowConfig:
    return WorkflowConfig(
        workflows={
            "article": WorkflowDefinitionConfig(
                type=WorkflowType.WORKFLOW,
                places=("draft", "published"),
                transitions=(
                    TransitionConfig("publish", froms="draft", tos="published", guard=is_editor),
                ),
            ),
            "pull_request": WorkflowDefinitionConfig(
                places=("start", "review", "merged"),
                transitions={
                    "submit": TransitionConfig(froms="start", tos="review"),
                    "merge": TransitionConfig(froms="review", tos="merged"),
                },
            ),
        },
    )
