"""The workflows of the application, as the upstream bundle tests configure them."""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.fixtures.app_workflow.subjects import Article, PullRequest, Ticket
from tests.fixtures.definition_validator import DefinitionValidator
from xtr_workflow import WorkflowType
from xtr_workflow.bundle import (
    MarkingStoreConfig,
    PlaceConfig,
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
                supports=Article,
                definition_validators=(DefinitionValidator,),
                initial_marking="draft",
                metadata={"title": "article workflow", "description": "workflow for articles"},
                places=(
                    "draft",
                    "wait_for_journalist",
                    "approved_by_journalist",
                    "wait_for_spellchecker",
                    "approved_by_spellchecker",
                    "published",
                ),
                transitions={
                    "request_review": TransitionConfig(
                        froms="draft", tos=("wait_for_journalist", "wait_for_spellchecker")
                    ),
                    "journalist_approval": TransitionConfig(
                        froms="wait_for_journalist", tos="approved_by_journalist"
                    ),
                    "spellchecker_approval": TransitionConfig(
                        froms="wait_for_spellchecker", tos="approved_by_spellchecker"
                    ),
                    "publish": TransitionConfig(
                        froms=("approved_by_journalist", "approved_by_spellchecker"),
                        tos="published",
                    ),
                },
            ),
            "pull_request": WorkflowDefinitionConfig(
                supports=PullRequest,
                initial_marking="start",
                metadata={"title": "workflow title"},
                places={
                    "start_name_not_used": PlaceConfig(
                        "start", metadata={"title": "place start title"}
                    ),
                    "coding": None,
                    "travis": None,
                    "review": None,
                    "merged": None,
                    "closed": None,
                },
                transitions={
                    "submit": TransitionConfig(
                        froms="start",
                        tos="travis",
                        metadata={"title": "transition submit title"},
                    ),
                    "update": TransitionConfig(froms=("coding", "travis", "review"), tos="travis"),
                    "wait_for_review": TransitionConfig(froms="travis", tos="review"),
                    "request_change": TransitionConfig(froms="review", tos="coding"),
                    "accept": TransitionConfig(froms="review", tos="merged"),
                    "reject": TransitionConfig(froms="review", tos="closed"),
                    "reopen": TransitionConfig(froms="closed", tos="review"),
                },
            ),
            "service_marking_store_workflow": WorkflowDefinitionConfig(
                type=WorkflowType.WORKFLOW,
                marking_store=MarkingStoreConfig(service="workflow_service"),
                supports=Ticket,
                places=(PlaceConfig("first"), PlaceConfig("last")),
                transitions={"go": TransitionConfig(froms="first", tos="last")},
            ),
            "by_strategy": WorkflowDefinitionConfig(
                type=WorkflowType.WORKFLOW,
                support_strategy="ticket_support",
                places=("draft", "published"),
                transitions={"publish": TransitionConfig(froms="draft", tos="published")},
            ),
            "injected_only": WorkflowDefinitionConfig(
                places=("first", "last"),
                transitions={"go": TransitionConfig(froms="first", tos="last")},
            ),
        },
    )
