"""A transition moves tokens along its arcs, and is known by its identity."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_workflow import Arc, Transition

if TYPE_CHECKING:
    from collections.abc import Sequence


@pytest.mark.parametrize(
    ("froms", "tos"),
    [
        pytest.param("a", "b", id="plain-strings"),
        pytest.param(["a"], ["b"], id="sequences-of-strings"),
        pytest.param([Arc("a", 1)], [Arc("b", 1)], id="sequences-of-arcs"),
        pytest.param(Arc("a", 1), Arc("b", 1), id="single-arcs"),
    ],
)
def test_it_turns_what_it_is_given_into_arcs(
    froms: str | Arc | Sequence[str | Arc],
    tos: str | Arc | Sequence[str | Arc],
) -> None:
    transition = Transition("name", froms, tos)

    assert transition.get_froms(as_arc=True) == [Arc("a", 1)]
    assert transition.get_tos(as_arc=True) == [Arc("b", 1)]


def test_it_keeps_its_name() -> None:
    assert Transition("name", "a", "b").get_name() == "name"


def test_it_keeps_its_arcs_in_the_order_they_were_given() -> None:
    transition = Transition("name", ["a", Arc("b", 2)], "c")

    assert transition.get_froms(as_arc=True) == [Arc("a", 1), Arc("b", 2)]


def test_an_arc_that_is_neither_a_place_name_nor_an_arc_is_refused() -> None:
    with pytest.raises(TypeError) as raised:
        _ = Transition("name", [True], ["a"])  # ty: ignore[invalid-argument-type] # pyright: ignore[reportArgumentType] — a wrong arc is what the check refuses

    assert str(raised.value) == 'The type of arc is invalid. Expected string or Arc, got "bool".'


def test_it_gives_place_names_unless_asked_for_arcs() -> None:
    transition = Transition("name", "a", "b")

    assert transition.get_froms() == ["a"]
    assert transition.get_tos() == ["b"]


def test_two_transitions_alike_are_two_transitions() -> None:
    first = Transition("name", "a", "b")
    second = Transition("name", "a", "b")

    assert first != second
    assert len({first, second}) == 2
