"""A state machine validator refuses a definition a state machine cannot run."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_workflow import Arc, Definition, Transition
from xtr_workflow.exception import InvalidDefinitionError
from xtr_workflow.validator import StateMachineValidator

if TYPE_CHECKING:
    from collections.abc import Sequence


def test_two_transitions_of_one_name_leaving_the_same_place_are_refused() -> None:
    definition = Definition(
        ["a", "b", "c"],
        [Transition("t1", "a", "b"), Transition("t1", "a", "c")],
    )

    with pytest.raises(InvalidDefinitionError) as raised:
        StateMachineValidator().validate(definition, "foo")

    assert str(raised.value) == (
        "A transition from a place/state must have an unique name. Multiple transitions named "
        '"t1" from place/state "a" were found on StateMachine "foo".'
    )


@pytest.mark.parametrize(
    ("tos", "outputs"),
    [
        pytest.param(["b", "c"], 2, id="several"),
        pytest.param([], 0, id="none"),
    ],
)
def test_a_transition_without_exactly_one_output_is_refused(
    tos: Sequence[str], outputs: int
) -> None:
    definition = Definition(["a", "b", "c"], [Transition("t1", "a", tos)])

    with pytest.raises(InvalidDefinitionError) as raised:
        StateMachineValidator().validate(definition, "foo")

    assert str(raised.value) == (
        "A transition in StateMachine can only have one output. But the transition "
        f'"t1" in StateMachine "foo" has {outputs} outputs.'
    )


@pytest.mark.parametrize(
    ("froms", "inputs"),
    [
        pytest.param(["a", "b"], 2, id="several"),
        pytest.param([], 0, id="none"),
    ],
)
def test_a_transition_without_exactly_one_input_is_refused(
    froms: Sequence[str], inputs: int
) -> None:
    definition = Definition(["a", "b", "c"], [Transition("t1", froms, "c")])

    with pytest.raises(InvalidDefinitionError) as raised:
        StateMachineValidator().validate(definition, "foo")

    assert str(raised.value) == (
        "A transition in StateMachine can only have one input. But the transition "
        f'"t1" in StateMachine "foo" has {inputs} inputs.'
    )


def test_transitions_of_different_names_may_leave_the_same_place() -> None:
    definition = Definition(
        ["a", "b", "c"],
        [Transition("t1", "a", "b"), Transition("t2", "a", "c")],
    )

    StateMachineValidator().validate(definition, "foo")


def test_transitions_of_one_name_may_leave_different_places() -> None:
    definition = Definition(
        ["a", "b", "c"],
        [Transition("t1", "a", "b"), Transition("t1", "b", "c")],
    )

    StateMachineValidator().validate(definition, "foo")


def test_several_initial_places_are_refused() -> None:
    definition = Definition(["a", "b", "c"], [], ["a", "b"])

    with pytest.raises(InvalidDefinitionError) as raised:
        StateMachineValidator().validate(definition, "foo")

    assert str(raised.value) == (
        'The state machine "foo" cannot store many places. But the definition has 2 initial '
        "places. Only one is supported."
    )


def test_an_arc_into_a_transition_weighing_more_than_one_is_refused() -> None:
    definition = Definition(["a", "b"], [Transition("t1", [Arc("a", 2)], [Arc("b", 1)])])

    with pytest.raises(InvalidDefinitionError) as raised:
        StateMachineValidator().validate(definition, "foo")

    assert str(raised.value) == (
        "A transition in StateMachine can only have arc with weight equals to one. But the "
        'transition "t1" in StateMachine "foo" has an arc from "a" to the transition with a '
        "weight equals to 2."
    )


def test_an_arc_out_of_a_transition_weighing_more_than_one_is_refused() -> None:
    definition = Definition(["a", "b"], [Transition("t1", [Arc("a", 1)], [Arc("b", 2)])])

    with pytest.raises(InvalidDefinitionError) as raised:
        StateMachineValidator().validate(definition, "foo")

    assert str(raised.value) == (
        "A transition in StateMachine can only have arc with weight equals to one. But the "
        'transition "t1" in StateMachine "foo" has an arc from the transition to "b" with a '
        "weight equals to 2."
    )
