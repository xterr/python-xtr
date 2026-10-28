"""An in-memory store keeps the metadata it is built with, a transition's by the transition."""

from __future__ import annotations

import pytest

from xtr_workflow import Transition
from xtr_workflow.metadata import InMemoryMetadataStore

TRANSITION = Transition("transition_1", [], [])


@pytest.fixture
def store() -> InMemoryMetadataStore:
    return InMemoryMetadataStore(
        {"title": "workflow title"},
        {"place_a": {"title": "place_a title"}},
        {TRANSITION: {"title": "transition_1 title"}},
    )


def test_it_returns_the_workflow_metadata(store: InMemoryMetadataStore) -> None:
    assert store.get_workflow_metadata()["title"] == "workflow title"


def test_a_place_it_holds_nothing_for_has_empty_metadata(store: InMemoryMetadataStore) -> None:
    assert store.get_place_metadata("place_b") == {}


def test_it_returns_the_metadata_of_a_place(store: InMemoryMetadataStore) -> None:
    assert store.get_place_metadata("place_a")["title"] == "place_a title"


def test_a_transition_it_holds_nothing_for_has_empty_metadata(
    store: InMemoryMetadataStore,
) -> None:
    assert store.get_transition_metadata(Transition("transition_2", [], [])) == {}


def test_it_returns_the_metadata_of_a_transition(store: InMemoryMetadataStore) -> None:
    assert store.get_transition_metadata(TRANSITION)["title"] == "transition_1 title"


def test_a_transition_built_alike_does_not_share_its_metadata(
    store: InMemoryMetadataStore,
) -> None:
    assert store.get_transition_metadata(Transition("transition_1", [], [])) == {}


def test_an_entry_is_read_from_the_workflow_when_no_subject_is_named(
    store: InMemoryMetadataStore,
) -> None:
    assert store.get_metadata("title") == "workflow title"


def test_an_entry_is_read_from_the_place_named(store: InMemoryMetadataStore) -> None:
    assert store.get_metadata("title", "place_a") == "place_a title"


def test_an_entry_is_read_from_the_transition_given(store: InMemoryMetadataStore) -> None:
    assert store.get_metadata("title", TRANSITION) == "transition_1 title"


@pytest.mark.parametrize(
    "subject",
    [
        pytest.param(None, id="workflow"),
        pytest.param("place_a", id="place-with-metadata"),
        pytest.param("place_b", id="place-without-metadata"),
        pytest.param(TRANSITION, id="transition-with-metadata"),
        pytest.param(Transition("transition_2", [], []), id="transition-without-metadata"),
    ],
)
def test_an_entry_its_subject_lacks_is_none(
    store: InMemoryMetadataStore,
    subject: str | Transition | None,
) -> None:
    assert store.get_metadata("description", subject) is None


def test_it_holds_no_metadata_unless_given_some() -> None:
    store = InMemoryMetadataStore()

    assert store.get_workflow_metadata() == {}
    assert store.get_place_metadata("place_a") == {}
    assert store.get_transition_metadata(TRANSITION) == {}


def test_changing_the_metadata_it_was_built_with_leaves_it_unchanged() -> None:
    places_metadata = {"place_a": {"title": "place_a title"}}
    store = InMemoryMetadataStore(places_metadata=places_metadata)

    places_metadata["place_a"]["title"] = "changed"

    assert store.get_place_metadata("place_a") == {"title": "place_a title"}


def test_changing_the_metadata_it_returns_leaves_it_unchanged(
    store: InMemoryMetadataStore,
) -> None:
    store.get_place_metadata("place_a")["title"] = "changed"

    assert store.get_place_metadata("place_a") == {"title": "place_a title"}
