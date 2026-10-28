"""A workflow whose publication needs an editor, and whose archiving needs no one."""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.fixtures.app_workflow_guards.guards import is_anonymous, is_editor
from tests.fixtures.subject import Subject
from xtr_workflow import WorkflowType
from xtr_workflow.bundle import TransitionConfig, WorkflowConfig, WorkflowDefinitionConfig


@configure
def workflow() -> WorkflowConfig:
    return WorkflowConfig(
        workflows={
            "article": WorkflowDefinitionConfig(
                type=WorkflowType.WORKFLOW,
                supports=Subject,
                places=("draft", "published", "archived"),
                transitions=(
                    TransitionConfig("publish", froms="draft", tos="published", guard=is_editor),
                    TransitionConfig("archive", froms="draft", tos="archived", guard=is_anonymous),
                ),
            ),
        },
    )
