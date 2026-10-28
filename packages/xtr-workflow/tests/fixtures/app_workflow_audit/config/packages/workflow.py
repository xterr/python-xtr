"""An audited workflow, and one beside it that is not."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_workflow import WorkflowType
from xtr_workflow.bundle import (
    AuditTrailConfig,
    TransitionConfig,
    WorkflowConfig,
    WorkflowDefinitionConfig,
)


@configure
def workflow() -> WorkflowConfig:
    return WorkflowConfig(
        workflows={
            "article": WorkflowDefinitionConfig(
                type=WorkflowType.WORKFLOW,
                audit_trail=AuditTrailConfig(enabled=True),
                places=("draft", "published"),
                transitions={"publish": TransitionConfig(froms="draft", tos="published")},
            ),
            "silent": WorkflowDefinitionConfig(
                type=WorkflowType.WORKFLOW,
                places=("draft", "published"),
                transitions={"publish": TransitionConfig(froms="draft", tos="published")},
            ),
        },
    )
