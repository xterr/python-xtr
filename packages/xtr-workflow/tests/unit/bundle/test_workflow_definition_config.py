"""A workflow's configuration reads every shorthand into one shape, and refuses what cannot run."""

from __future__ import annotations

from enum import StrEnum
from typing import cast, final

import pytest

from tests.fixtures.definition_validator import DefinitionValidator
from xtr_workflow import WorkflowType
from xtr_workflow.bundle import (
    ArcConfig,
    AuditTrailConfig,
    PlaceConfig,
    TransitionConfig,
    WorkflowDefinitionConfig,
)
from xtr_workflow.exception import InvalidArgumentError
from xtr_workflow.validator import DefinitionValidatorInterface

_GO = (TransitionConfig("go", "a", "b"),)


class Places(StrEnum):
    A = "a"
    B = "b"
    C = "c"


class _NotAValidator:
    pass


@final
class _ValidatorNeedingArguments:
    def __init__(self, strict: bool) -> None:
        self.strict = strict

    def validate(self, definition: object, name: str) -> None:
        del definition, name


def test_enum_arcs_are_normalized() -> None:
    config = WorkflowDefinitionConfig(
        supports=(object,),
        places=tuple(Places),
        initial_marking=Places.A,
        transitions=(
            TransitionConfig("one", [Places.A], [ArcConfig(Places.B, 2)]),
            TransitionConfig("two", ArcConfig(Places.B, 3), ArcConfig(Places.C)),
        ),
    )

    assert config.initial_marking == ("a",)
    one, two = config.transitions
    assert one.name == "one"
    assert one.froms == (ArcConfig("a", 1),)
    assert one.tos == (ArcConfig("b", 2),)
    assert two.name == "two"
    assert two.froms == (ArcConfig("b", 3),)
    assert two.tos == (ArcConfig("c", 1),)


def test_places_and_transitions_given_as_mappings_are_named_by_their_keys() -> None:
    config = WorkflowDefinitionConfig(
        supports=(object,),
        places={"draft": None, "review": PlaceConfig(metadata={"description": "Human review"})},
        transitions={
            "to_review": TransitionConfig(froms="draft", tos="review"),
            "reopen": TransitionConfig(froms="review", tos="draft"),
        },
    )

    assert config.places == (
        PlaceConfig("draft"),
        PlaceConfig("review", {"description": "Human review"}),
    )
    assert [transition.name for transition in config.transitions] == ["to_review", "reopen"]


def test_a_place_keyed_by_one_name_keeps_its_own() -> None:
    config = WorkflowDefinitionConfig(places={"draft": PlaceConfig("review")}, transitions=_GO)

    assert config.places == (PlaceConfig("review"),)


def test_a_transition_keyed_by_one_name_keeps_its_own() -> None:
    config = WorkflowDefinitionConfig(
        transitions={"go": TransitionConfig("publish", froms="a", tos="b")}
    )

    assert config.transitions[0].name == "publish"


def test_places_given_by_name_or_enum_member_are_places() -> None:
    config = WorkflowDefinitionConfig(
        places=("draft", Places.B, PlaceConfig("c", {"color": "blue"})), transitions=_GO
    )

    assert config.places == (
        PlaceConfig("draft"),
        PlaceConfig("b"),
        PlaceConfig("c", {"color": "blue"}),
    )


def test_a_single_place_is_one_place() -> None:
    config = WorkflowDefinitionConfig(places="draft", transitions=_GO)

    assert config.places == (PlaceConfig("draft"),)


def test_a_single_supported_class_and_initial_place_are_wrapped() -> None:
    config = WorkflowDefinitionConfig(supports=dict, initial_marking="a", transitions=_GO)

    assert config.supports == (dict,)
    assert config.initial_marking == ("a",)


def test_the_defaults_mirror_a_state_machine_with_nothing_else_set() -> None:
    config = WorkflowDefinitionConfig(transitions=_GO)

    assert config.audit_trail == AuditTrailConfig()
    assert config.type is WorkflowType.STATE_MACHINE
    assert config.marking_store is None
    assert config.supports == ()
    assert config.definition_validators == ()
    assert config.support_strategy is None
    assert config.initial_marking == ()
    assert config.events_to_dispatch is None
    assert config.places == ()
    assert config.metadata == {}


def test_events_to_dispatch_rejects_mixed_allow_list_and_block_list() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(
            events_to_dispatch=("workflow.enter", "!workflow.announce"), transitions=_GO
        )

    assert str(raised.value) == (
        'Cannot mix allow-list and block-list entries in "events_to_dispatch": every entry must '
        'start with "!" (block-list mode) or none of them must (allow-list mode).'
    )


def test_events_to_dispatch_accepts_a_block_list_only() -> None:
    config = WorkflowDefinitionConfig(events_to_dispatch=["!workflow.announce"], transitions=_GO)

    assert config.events_to_dispatch == ("!workflow.announce",)


def test_events_to_dispatch_accepts_none_of_them() -> None:
    assert WorkflowDefinitionConfig(events_to_dispatch=(), transitions=_GO).events_to_dispatch == ()


def test_events_to_dispatch_rejects_a_block_listed_guard_event() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(events_to_dispatch=("!workflow.guard",), transitions=_GO)

    assert str(raised.value) == (
        'The "workflow.guard" event cannot be disabled in "events_to_dispatch": it is always '
        "dispatched."
    )


@pytest.mark.parametrize("event", ["workflow.unknown", "!workflow.unknown"])
def test_events_to_dispatch_rejects_an_unknown_event(event: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(events_to_dispatch=(event,), transitions=_GO)

    assert str(raised.value) == (
        'The value must be "null" or an array of workflow events (like ["workflow.enter"]). '
        'Prefix an event with "!" to disable it (e.g. ["!workflow.announce"]).'
    )


def test_supports_and_support_strategy_cannot_be_used_together() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(
            supports=(object,), support_strategy="app.support_strategy", transitions=_GO
        )

    assert str(raised.value) == '"supports" and "support_strategy" cannot be used together.'


def test_a_workflow_needs_a_transition() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(transitions=())

    assert str(raised.value) == (
        'The "transitions" option should have at least 1 element(s) defined.'
    )


def test_a_transition_needs_a_name() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(transitions=(TransitionConfig(froms="a", tos="b"),))

    assert str(raised.value) == (
        'The "name" option is required for each transition in workflow configuration.'
    )


@pytest.mark.parametrize(
    ("transition", "option"),
    [(TransitionConfig("go", tos="b"), "froms"), (TransitionConfig("go", froms="a"), "tos")],
)
def test_a_transition_needs_an_arc_each_way(transition: TransitionConfig, option: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(transitions=(transition,))

    assert str(raised.value) == (
        f'The "{option}" option of the transition "go" should have at least 1 element(s) defined.'
    )


def test_a_place_needs_a_name() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(places=(PlaceConfig(),), transitions=_GO)

    assert str(raised.value) == 'The name of a place cannot contain an empty value, but got "".'


def test_definition_validators_are_kept_in_order() -> None:
    config = WorkflowDefinitionConfig(definition_validators=[DefinitionValidator], transitions=_GO)

    assert config.definition_validators == (DefinitionValidator,)


def test_a_definition_validator_must_implement_the_interface() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(
            definition_validators=(cast("type[DefinitionValidatorInterface]", _NotAValidator),),
            transitions=_GO,
        )

    assert str(raised.value) == (
        f'The validation class "{__name__}._NotAValidator" is not an instance of '
        '"xtr_workflow.validator.definition_validator_interface.DefinitionValidatorInterface".'
    )


def test_a_definition_validator_must_build_with_no_arguments() -> None:
    assert isinstance(_ValidatorNeedingArguments(strict=True), DefinitionValidatorInterface)

    with pytest.raises(InvalidArgumentError) as raised:
        _ = WorkflowDefinitionConfig(
            definition_validators=(_ValidatorNeedingArguments,), transitions=_GO
        )

    assert str(raised.value) == (
        f'The "{__name__}._ValidatorNeedingArguments" validation class constructor must not '
        "have any arguments."
    )
