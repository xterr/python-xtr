"""A configured ``task`` workflow."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_workflow.bundle import TransitionConfig, WorkflowConfig, WorkflowDefinitionConfig


@configure
def workflow() -> WorkflowConfig:
    return WorkflowConfig(
        workflows={
            "task": WorkflowDefinitionConfig(
                supports=object,
                places=("a", "b"),
                transitions={"go": TransitionConfig(froms="a", tos="b")},
            ),
        },
    )
