"""A workflow validator refuses a definition its workflow cannot run."""

from __future__ import annotations

import pytest

from xtr_workflow import Arc, Definition, Transition
from xtr_workflow.exception import InvalidDefinitionError
from xtr_workflow.validator import WorkflowValidator

# What a workflow keeping a single place per subject cannot run, and any other workflow can.
SEVERAL_OUTPUTS = Definition(["a", "b", "c"], [Transition("t1", "a", ["b", "c"])])
SEVERAL_INITIAL_PLACES = Definition(["a", "b", "c"], [Transition("t1", "a", "b")], ["a", "b"])
HEAVY_ARC_IN = Definition(["a", "b"], [Transition("t1", [Arc("a", 2)], [Arc("b", 1)])])
HEAVY_ARC_OUT = Definition(["a", "b"], [Transition("t1", [Arc("a", 1)], [Arc("b", 2)])])


@pytest.mark.parametrize("single_place", [False, True], ids=["many-places", "single-place"])
def test_two_transitions_of_one_name_leaving_the_same_place_are_refused(single_place: bool) -> None:
    definition = Definition(
        ["a", "b", "c"],
        [Transition("t0", "c", "b"), Transition("t1", "a", "b"), Transition("t1", "a", "c")],
    )

    with pytest.raises(InvalidDefinitionError) as raised:
        WorkflowValidator(single_place=single_place).validate(definition, "foo")

    assert str(raised.value) == (
        "All transitions for a place must have an unique name. Multiple transitions named "
        '"t1" where found for place "a" in workflow "foo".'
    )


def test_two_transitions_of_one_name_sharing_any_place_they_leave_are_refused() -> None:
    definition = Definition(
        ["a", "b", "c", "d"],
        [Transition("t1", ["a", "b"], "c"), Transition("t1", "b", "d")],
    )

    with pytest.raises(InvalidDefinitionError) as raised:
        WorkflowValidator().validate(definition, "foo")

    assert str(raised.value) == (
        "All transitions for a place must have an unique name. Multiple transitions named "
        '"t1" where found for place "b" in workflow "foo".'
    )


def test_transitions_of_one_name_may_leave_different_places() -> None:
    definition = Definition(
        ["a", "b", "c", "d"],
        [Transition("t1", "a", "b"), Transition("t1", "b", "c"), Transition("t1", "d", "c")],
    )

    WorkflowValidator().validate(definition, "foo")


def test_single_place_refuses_a_transition_with_several_outputs() -> None:
    with pytest.raises(InvalidDefinitionError) as raised:
        WorkflowValidator(single_place=True).validate(SEVERAL_OUTPUTS, "foo")

    assert str(raised.value) == (
        'The marking store of workflow "foo" cannot store many places. But the transition "t1" '
        "has too many output (2). Only one is accepted."
    )


def test_single_place_refuses_several_initial_places() -> None:
    with pytest.raises(InvalidDefinitionError) as raised:
        WorkflowValidator(single_place=True).validate(SEVERAL_INITIAL_PLACES, "foo")

    assert str(raised.value) == (
        'The marking store of workflow "foo" cannot store many places. But the definition has 2 '
        "initial places. Only one is supported."
    )


def test_single_place_refuses_an_arc_into_a_transition_weighing_more_than_one() -> None:
    with pytest.raises(InvalidDefinitionError) as raised:
        WorkflowValidator(single_place=True).validate(HEAVY_ARC_IN, "foo")

    assert str(raised.value) == (
        'The marking store of workflow "foo" cannot store many places. But the transition "t1" '
        'has an arc from place "a" with a weight of 2.'
    )


def test_single_place_refuses_an_arc_out_of_a_transition_weighing_more_than_one() -> None:
    with pytest.raises(InvalidDefinitionError) as raised:
        WorkflowValidator(single_place=True).validate(HEAVY_ARC_OUT, "foo")

    assert str(raised.value) == (
        'The marking store of workflow "foo" cannot store many places. But the transition "t1" '
        'has an arc to place "b" with a weight of 2.'
    )


def test_single_place_accepts_one_token_moving_from_place_to_place() -> None:
    definition = Definition(
        ["a", "b", "c"],
        [Transition("t1", "a", "b"), Transition("t2", "b", "c")],
    )

    WorkflowValidator(single_place=True).validate(definition, "foo")


@pytest.mark.parametrize(
    "definition",
    [
        pytest.param(SEVERAL_OUTPUTS, id="several-outputs"),
        pytest.param(SEVERAL_INITIAL_PLACES, id="several-initial-places"),
        pytest.param(HEAVY_ARC_IN, id="heavy-arc-in"),
        pytest.param(HEAVY_ARC_OUT, id="heavy-arc-out"),
    ],
)
def test_without_single_place_what_it_refuses_is_accepted(definition: Definition) -> None:
    WorkflowValidator().validate(definition, "foo")
