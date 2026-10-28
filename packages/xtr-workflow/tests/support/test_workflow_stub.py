"""The workflow stub keeps its own contract: it is a workflow, answering what it was built with."""

from __future__ import annotations

from tests.support.workflow_stub import WorkflowStub
from xtr_workflow import Definition, WorkflowInterface
from xtr_workflow.marking_store import MethodMarkingStore
from xtr_workflow.metadata import InMemoryMetadataStore


def test_it_is_a_workflow() -> None:
    assert isinstance(WorkflowStub(), WorkflowInterface)


def test_it_answers_with_what_it_was_built_with() -> None:
    metadata_store = InMemoryMetadataStore()
    definition = Definition(["a"], [], metadata_store=metadata_store)
    marking_store = MethodMarkingStore()

    workflow = WorkflowStub("post", definition, marking_store)

    assert workflow.get_name() == "post"
    assert workflow.get_definition() is definition
    assert workflow.get_marking_store() is marking_store
    assert workflow.get_metadata_store() is metadata_store


def test_it_has_an_empty_definition_and_a_method_marking_store_unless_given_others() -> None:
    workflow = WorkflowStub()

    assert workflow.get_name() == "article"
    assert workflow.get_definition().get_places() == {}
    assert isinstance(workflow.get_marking_store(), MethodMarkingStore)
