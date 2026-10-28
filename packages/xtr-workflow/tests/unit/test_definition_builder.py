"""A definition builder assembles a definition a step at a time."""

from __future__ import annotations

from xtr_workflow import DefinitionBuilder, Transition
from xtr_workflow.metadata import InMemoryMetadataStore


def test_it_builds_with_the_initial_places_it_is_told() -> None:
    builder = DefinitionBuilder(["a", "b"])
    _ = builder.set_initial_places("b")

    assert builder.build().get_initial_places() == ["b"]


def test_it_builds_with_the_transitions_it_is_given_then_those_added() -> None:
    transition0 = Transition("name0", "a", "b")
    transition1 = Transition("name1", "a", "b")
    builder = DefinitionBuilder(["a", "b"], [transition0])
    _ = builder.add_transition(transition1)

    first, second = builder.build().get_transitions()

    assert first is transition0
    assert second is transition1


def test_it_builds_with_the_places_it_is_given_then_those_added() -> None:
    builder = DefinitionBuilder(["a"], [])
    _ = builder.add_place("b")

    assert builder.build().get_places() == {"a": "a", "b": "b"}


def test_it_builds_with_the_metadata_store_it_is_given() -> None:
    store = InMemoryMetadataStore()
    builder = DefinitionBuilder(["a"])
    _ = builder.set_metadata_store(store)

    assert builder.build().get_metadata_store() is store


def test_the_first_place_added_is_the_initial_place_over_one_told_before() -> None:
    builder = DefinitionBuilder().set_initial_places("b")

    definition = builder.add_places(["a", "b"]).build()

    assert definition.get_initial_places() == ["a"]


def test_clearing_it_forgets_everything_it_was_given() -> None:
    store = InMemoryMetadataStore()
    builder = (
        DefinitionBuilder(["a", "b"], [Transition("name", "a", "b")])
        .set_initial_places("b")
        .set_metadata_store(store)
    )

    definition = builder.clear().build()

    assert definition.get_places() == {}
    assert definition.get_transitions() == []
    assert definition.get_initial_places() == []
    assert definition.get_metadata_store() is not store


def test_every_step_returns_the_builder() -> None:
    builder = DefinitionBuilder()

    returned = [
        builder.clear(),
        builder.set_initial_places(None),
        builder.add_place("a"),
        builder.add_places(["b"]),
        builder.add_transition(Transition("name", "a", "b")),
        builder.add_transitions([]),
        builder.set_metadata_store(InMemoryMetadataStore()),
    ]

    assert all(step is builder for step in returned)
