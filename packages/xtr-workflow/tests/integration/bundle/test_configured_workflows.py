"""A kernel registers every configured workflow, its definition, and the registry finding them."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test

from tests.fixtures.app_workflow.services import Journal, WorkflowConsumer
from tests.fixtures.app_workflow.subjects import Article, PullRequest, Ticket
from tests.fixtures.definition_validator import DefinitionValidator
from xtr_workflow import (
    Definition,
    MarkingStoreInterface,
    Registry,
    StateMachine,
    Workflow,
    WorkflowInterface,
)
from xtr_workflow.debug import TraceableWorkflow
from xtr_workflow.exception import InvalidArgumentError
from xtr_workflow.metadata import InMemoryMetadataStore

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    from xtr_dependency_injection import BootedKernel

pytestmark = pytest.mark.anyio


async def booted(*, debug: bool = False) -> AbstractAsyncContextManager[BootedKernel]:
    return await boot_for_test(Kernel("tests.fixtures.app_workflow", env="test", debug=debug))


async def test_each_workflow_is_registered_under_its_name() -> None:
    async with await booted() as kernel:
        article = await kernel.container.get(WorkflowInterface, "article")
        pull_request = await kernel.container.get(WorkflowInterface, "pull_request")

    assert type(article) is Workflow
    assert article.get_name() == "article"
    assert type(pull_request) is StateMachine
    assert pull_request.get_name() == "pull_request"


async def test_the_definition_is_built_from_the_configuration_and_validated() -> None:
    DefinitionValidator.calls.clear()

    async with await booted() as kernel:
        definition = await kernel.container.get(Definition, "article")
        workflow = await kernel.container.get(WorkflowInterface, "article")

    assert list(definition.get_places()) == [
        "draft",
        "wait_for_journalist",
        "approved_by_journalist",
        "wait_for_spellchecker",
        "approved_by_spellchecker",
        "published",
    ]
    assert len(definition.get_transitions()) == 4
    assert definition.get_initial_places() == ["draft"]
    assert workflow.get_definition() is definition
    assert DefinitionValidator.calls == [(definition, "article")]


async def test_a_state_machine_gets_one_transition_per_pair_of_places() -> None:
    async with await booted() as kernel:
        definition = await kernel.container.get(Definition, "pull_request")
        metadata_store = await kernel.container.get(InMemoryMetadataStore, "pull_request")

    transitions = definition.get_transitions()
    assert list(definition.get_places()) == [
        "start",
        "coding",
        "travis",
        "review",
        "merged",
        "closed",
    ]
    assert len(transitions) == 9
    assert definition.get_initial_places() == ["start"]
    assert definition.get_metadata_store() is metadata_store
    assert metadata_store.get_workflow_metadata() == {"title": "workflow title"}
    assert metadata_store.get_place_metadata("start") == {"title": "place start title"}
    assert metadata_store.get_transition_metadata(transitions[0]) == {
        "title": "transition submit title"
    }


async def test_a_workflow_keeps_its_markings_in_the_service_its_configuration_names() -> None:
    async with await booted() as kernel:
        workflow = await kernel.container.get(WorkflowInterface, "service_marking_store_workflow")
        store = await kernel.container.get(MarkingStoreInterface, "workflow_service")

    assert workflow.get_marking_store() is store


async def test_the_registry_finds_each_workflow_by_the_subjects_it_supports() -> None:
    async with await booted() as kernel:
        registry = await kernel.container.get(Registry)
        article = await kernel.container.get(WorkflowInterface, "article")
        pull_request = await kernel.container.get(WorkflowInterface, "pull_request")
        ticket_workflows = registry.all(Ticket())

    assert registry.all(Article()) == [article]
    assert registry.all(PullRequest()) == [pull_request]
    assert [workflow.get_name() for workflow in ticket_workflows] == [
        "service_marking_store_workflow",
        "by_strategy",
    ]


async def test_a_workflow_supporting_nothing_is_only_injected() -> None:
    async with await booted() as kernel:
        registry = await kernel.container.get(Registry)
        injected = await kernel.container.get(WorkflowInterface, "injected_only")

    assert injected.get_name() == "injected_only"
    assert all(workflow.get_name() != "injected_only" for workflow in registry.all(object()))
    with pytest.raises(InvalidArgumentError, match='Unable to find a workflow for class "object"'):
        _ = registry.get(object())


async def test_a_listener_declaring_the_guard_event_by_its_class_hears_it() -> None:
    async with await booted() as kernel:
        workflow = await kernel.container.get(WorkflowInterface, "article")
        journal = await kernel.container.get(Journal)

        _ = await workflow.apply(Article(), "request_review")

    assert "article.request_review" in journal.guarded


async def test_in_debug_mode_every_way_of_injecting_a_workflow_gives_the_traced_one() -> None:
    async with await booted(debug=True) as kernel:
        consumer = await kernel.container.get(WorkflowConsumer)
        located = await consumer.workflows.get("article")
        registry = await kernel.container.get(Registry)

        _ = await consumer.article.apply(Article(), "request_review")

    assert isinstance(consumer.article, TraceableWorkflow)
    assert located is consumer.article
    assert registry.all(Article()) == [consumer.article]
    assert type(consumer.article.get_inner()) is Workflow
    assert [call["method"] for call in consumer.article.get_calls()] == ["apply"]


async def test_out_of_debug_mode_no_workflow_is_traced() -> None:
    async with await booted() as kernel:
        consumer = await kernel.container.get(WorkflowConsumer)

    assert type(consumer.article) is Workflow
