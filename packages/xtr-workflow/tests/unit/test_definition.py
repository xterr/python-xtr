"""A definition holds a workflow's places and transitions, and the places a subject starts in."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_workflow import Definition, Transition
from xtr_workflow.exception import LogicError
from xtr_workflow.metadata import InMemoryMetadataStore

if TYPE_CHECKING:
    from collections.abc import Callable

PLACES = ["a", "b", "c", "d", "e"]


def test_it_holds_the_places_it_is_given() -> None:
    definition = Definition(PLACES, [])

    assert definition.get_places() == {"a": "a", "b": "b", "c": "c", "d": "d", "e": "e"}


def test_its_first_place_is_the_initial_place_unless_told_otherwise() -> None:
    assert Definition(PLACES, []).get_initial_places() == ["a"]


def test_it_takes_the_initial_place_it_is_given() -> None:
    assert Definition(PLACES, [], "d").get_initial_places() == ["d"]


def test_it_takes_the_initial_places_it_is_given() -> None:
    assert Definition(PLACES, [], ["a", "e"]).get_initial_places() == ["a", "e"]


def test_no_initial_place_given_as_an_empty_list_leaves_the_first_place_initial() -> None:
    assert Definition(PLACES, [], []).get_initial_places() == ["a"]


def test_an_initial_place_that_does_not_exist_is_refused() -> None:
    with pytest.raises(LogicError) as raised:
        _ = Definition([], [], "d")

    assert str(raised.value) == 'Place "d" cannot be the initial place as it does not exist.'


def test_it_holds_the_transitions_it_is_given() -> None:
    transition = Transition("name", "a", "b")

    [held] = Definition(["a", "b"], [transition]).get_transitions()

    assert held is transition


def test_a_place_a_transition_leaves_is_a_place_though_not_given() -> None:
    definition = Definition(["a", "b"], [Transition("name", "c", "b")])

    assert definition.get_places()["c"] == "c"


def test_a_place_a_transition_enters_is_a_place_though_not_given() -> None:
    definition = Definition(["a", "b"], [Transition("name", "a", "c")])

    assert definition.get_places()["c"] == "c"


def test_places_transitions_bring_follow_the_places_given_in_order() -> None:
    definition = Definition(["b", "a"], [Transition("name", ["c", "a"], "d")])

    assert list(definition.get_places()) == ["b", "a", "c", "d"]


def test_with_no_place_given_the_first_a_transition_brings_is_the_initial_place() -> None:
    assert Definition([], [Transition("name", "a", "b")]).get_initial_places() == ["a"]


def test_a_definition_without_places_has_no_initial_place() -> None:
    assert Definition([], []).get_initial_places() == []


def test_its_metadata_store_is_an_empty_in_memory_store_unless_given_one() -> None:
    store = Definition([], []).get_metadata_store()

    assert isinstance(store, InMemoryMetadataStore)
    assert store.get_workflow_metadata() == {}


def test_it_holds_the_metadata_store_it_is_given() -> None:
    store = InMemoryMetadataStore({"title": "workflow title"})

    assert Definition([], [], metadata_store=store).get_metadata_store() is store


@pytest.mark.parametrize(
    "read",
    [
        pytest.param(Definition.get_places, id="places"),
        pytest.param(Definition.get_transitions, id="transitions"),
        pytest.param(Definition.get_initial_places, id="initial-places"),
    ],
)
def test_clearing_what_it_returns_leaves_it_unchanged(
    read: Callable[[Definition], dict[str, str] | list[Transition] | list[str]],
) -> None:
    definition = Definition(["a", "b"], [Transition("name", "a", "b")])
    expected = read(definition).copy()

    read(definition).clear()

    assert read(definition) == expected
