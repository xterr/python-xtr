"""A class declaring a workflow is read into that workflow's configuration, keyed by its name."""

from __future__ import annotations

from collections.abc import Sized
from typing import Annotated, ClassVar

import pytest

from tests.fixtures import declared_workflows as declared
from tests.fixtures import invalid_declared_workflows as invalid
from tests.fixtures.definition_validator import DefinitionValidator
from tests.fixtures.pull_request_state_machine import PullRequestStateMachine
from xtr_workflow import WorkflowType
from xtr_workflow.bundle import (
    ArcConfig,
    AuditTrailConfig,
    MarkingStoreConfig,
    PlaceConfig,
    TransitionConfig,
    WorkflowDefinitionConfig,
)
from xtr_workflow.bundle._declared_workflows import workflows_declared_on
from xtr_workflow.decorator import Transition, as_workflow
from xtr_workflow.exception import InvalidArgumentError, LogicError

_INVALID = invalid.__name__


def _read(class_: type) -> tuple[str, WorkflowDefinitionConfig]:
    ((name, config),) = workflows_declared_on(class_)
    return name, config


def test_a_minimal_definition() -> None:
    assert workflows_declared_on(declared.TaskWorkflow) == (
        (
            "task",
            WorkflowDefinitionConfig(
                type=WorkflowType.STATE_MACHINE,
                supports=(object,),
                initial_marking=(),
                metadata={},
                audit_trail=AuditTrailConfig(enabled=False),
                definition_validators=(),
                places=(PlaceConfig("new"), PlaceConfig("processing"), PlaceConfig("done")),
                transitions=(
                    TransitionConfig("start", "new", "processing"),
                    TransitionConfig("finish", "processing", "done"),
                ),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("class_", "expected_name"),
    [
        (declared.TaskWorkflow, "task"),
        (PullRequestStateMachine, "pull_request"),
        (declared.OrderV2Workflow, "order_v2"),
        (declared.HTMLPageWorkflow, "html_page"),
        (declared.Reviewing, "reviewing"),
        (declared.NamedWorkflow, "explicit.name"),
    ],
)
def test_the_name_is_derived_from_the_class_name(class_: type, expected_name: str) -> None:
    assert _read(class_)[0] == expected_name


def test_a_full_definition() -> None:
    assert _read(declared.FullWorkflow) == (
        "full",
        WorkflowDefinitionConfig(
            type=WorkflowType.WORKFLOW,
            supports=(object, Sized),
            initial_marking=("new", "extra"),
            metadata={"title": "Full"},
            audit_trail=AuditTrailConfig(enabled=True),
            definition_validators=(DefinitionValidator,),
            # The places the transitions use first, then those no transition uses.
            places=(
                PlaceConfig("new", {"label": "New"}),
                PlaceConfig("processing", {"label": "Processing", "bg_color": "#eee"}),
                PlaceConfig("done"),
                PlaceConfig("failed"),
                PlaceConfig("extra", {"label": "Extra"}),
                PlaceConfig("archived"),
                PlaceConfig("orphan"),
            ),
            transitions=(
                TransitionConfig(
                    "start", "new", "processing", guard=declared.is_user, metadata={"color": "blue"}
                ),
                TransitionConfig("finish", "processing", "done"),
                TransitionConfig("finish", "failed", "done"),
                TransitionConfig(
                    "merge",
                    (ArcConfig("done", 2), ArcConfig("extra")),
                    "archived",
                    guard=declared.always,
                    metadata={"label": "Merge"},
                ),
            ),
            marking_store=MarkingStoreConfig(property="step"),
            events_to_dispatch=("!workflow.announce",),
        ),
    )


def test_a_support_strategy_and_a_marking_store() -> None:
    config = _read(declared.ServicesWorkflow)[1]

    assert config.supports == ()
    assert config.support_strategy == "app.support_strategy"
    assert config.marking_store == MarkingStoreConfig(service="app.marking_store")


def test_places_from_an_enum() -> None:
    assert _read(declared.EnumPlacesWorkflow)[1].places == (
        PlaceConfig("new", {"label": "New"}),
        PlaceConfig("processing", {"label": "Processing", "bg_color": "#eee"}),
        PlaceConfig("done"),
        PlaceConfig("failed"),
        PlaceConfig("archived"),
    )


def test_places_from_the_constants_of_the_class() -> None:
    assert _read(declared.PlaceConstantsWorkflow)[1].places == (
        PlaceConfig("draft", {"label": "Draft"}),
        PlaceConfig("published"),
        PlaceConfig("archived"),
    )


@pytest.mark.parametrize(
    ("class_", "expected_initial_marking"),
    [
        pytest.param(declared.TaskWorkflow, (), id="no initial place"),
        pytest.param(declared.InitialCaseStateMachine, ("draft",), id="initial enum member"),
        pytest.param(declared.InitialConstantStateMachine, ("pending",), id="initial constant"),
        pytest.param(declared.InitialPlacesWorkflow, ("draft", "review"), id="several"),
        pytest.param(
            declared.ExplicitInitialMarkingStateMachine, ("published",), id="explicit marking"
        ),
        pytest.param(
            declared.UnusedInitialCaseStateMachine, (), id="initial member not used by the workflow"
        ),
    ],
)
def test_the_initial_marking(class_: type, expected_initial_marking: tuple[str, ...]) -> None:
    assert _read(class_)[1].initial_marking == expected_initial_marking


def test_markers_with_metadata_on_constants_and_on_the_members_of_a_used_enum() -> None:
    config = _read(declared.MarkedPlacesWorkflow)[1]

    assert config.initial_marking == ("reviewed",)
    assert config.places == (
        PlaceConfig("draft", {"label": "Draft", "bg_color": "#eee"}),
        PlaceConfig("published"),
        PlaceConfig("reviewed", {"label": "Reviewed"}),
    )
    assert config.transitions == (
        TransitionConfig(
            "publish", "draft", "published", metadata={"label": "Publish", "async": True}
        ),
        TransitionConfig("publish", "reviewed", "published", metadata={"async": False}),
    )


def test_descriptions() -> None:
    name, config = _read(declared.DescribedArticleWorkflow)

    assert name == "article"
    assert config.metadata == {"title": "Articles", "description": "Manages the articles"}
    assert config.places == (
        PlaceConfig("draft", {"description": "Being written"}),
        PlaceConfig("published", {"label": "Published", "description": "Visible by everyone"}),
        PlaceConfig("archived"),
    )
    assert config.transitions == (
        TransitionConfig(
            "publish",
            "draft",
            "published",
            guard=declared.always,
            metadata={"description": "Makes the article public"},
        ),
        TransitionConfig("archive", "published", "archived"),
    )


def test_inherited_transitions_follow_the_class_own() -> None:
    config = _read(declared.InheritedTransitionsWorkflow)[1]

    assert [transition.name for transition in config.transitions] == ["back", "go"]


def test_a_constant_redeclared_by_the_class_hides_the_inherited_one() -> None:
    config = _read(declared.OverridingTransitionsWorkflow)[1]

    assert config.transitions == (TransitionConfig("go", "a", "c"),)


@pytest.mark.parametrize(
    ("class_", "expected_message"),
    [
        pytest.param(
            invalid.IntConstantWorkflow,
            f'The value of "{_INVALID}.IntConstantWorkflow.GO" must be a string to be used as the '
            'name of a transition, "int" given.',
            id="non-string transition constant",
        ),
        pytest.param(
            invalid.JoinStateMachine,
            f'The "go" transition of the state machine defined by "{_INVALID}.JoinStateMachine" '
            'must have exactly one input and one output place; repeat the "Transition" marker to '
            "define several transitions with the same name.",
            id="state machine transition from several places",
        ),
        pytest.param(
            invalid.SplitStateMachine,
            f'The "go" transition of the state machine defined by "{_INVALID}.SplitStateMachine" '
            'must have exactly one input and one output place; repeat the "Transition" marker to '
            "define several transitions with the same name.",
            id="state machine transition to several places",
        ),
        pytest.param(
            invalid.InvalidArcWorkflow,
            f'The places of the "go" transition of the workflow defined by "{_INVALID}.'
            'InvalidArcWorkflow" must be "xtr_workflow.arc.Arc" instances, enum cases or strings, '
            '"int" given.',
            id="invalid arc",
        ),
        pytest.param(
            invalid.IntEnumWorkflow,
            "Only string-backed enums can be used as places of the workflow defined by "
            f'"{_INVALID}.IntEnumWorkflow", "{_INVALID}.IntStep" is not.',
            id="int-valued enum",
        ),
        pytest.param(
            invalid.IntPlaceConstantWorkflow,
            f'The value of "{_INVALID}.IntPlaceConstantWorkflow.ONE" must be a string or a '
            'string-backed enum case to be used as the name of a place, "int" given.',
            id="non-string place constant",
        ),
        pytest.param(
            invalid.DuplicatePlaceWorkflow,
            f'The place "a" of the workflow defined by "{_INVALID}.DuplicatePlaceWorkflow" is '
            f'defined by both "{_INVALID}.DuplicatePlaceWorkflow.A" and '
            f'"{_INVALID}.DuplicatePlaceWorkflow.B".',
            id="duplicate place",
        ),
        pytest.param(
            invalid.PlacesFromClassWorkflow,
            f'The "places" argument of "@as_workflow" on "{_INVALID}.PlacesFromClassWorkflow" '
            'must be a string-backed enum, "builtins.object" given.',
            id="places from a class",
        ),
        pytest.param(
            invalid.PlaceNotInEnumWorkflow,
            f'The place "foreign" of the workflow defined by "{_INVALID}.PlaceNotInEnumWorkflow" '
            'is not a case of "tests.fixtures.declared_workflows.Step".',
            id="place not in the enum",
        ),
        pytest.param(
            invalid.SeveralPlaceMarkersWorkflow,
            f'"{_INVALID}.SeveralPlaceMarkersWorkflow.START" cannot have several "Place" markers.',
            id="several place markers on a constant",
        ),
    ],
)
def test_an_invalid_definition(class_: type, expected_message: str) -> None:
    with pytest.raises(LogicError) as raised:
        _ = workflows_declared_on(class_)

    assert str(raised.value) == expected_message


def test_an_empty_name_is_refused_when_the_class_is_declared() -> None:
    with pytest.raises(LogicError) as raised:

        @as_workflow(name="", supports=object)
        class EmptyNameWorkflow:
            GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"

    assert str(raised.value) == (
        f'The name of the workflow defined by "{__name__}.'
        'test_an_empty_name_is_refused_when_the_class_is_declared.<locals>.EmptyNameWorkflow" '
        "cannot be empty."
    )


def test_the_configuration_read_is_checked_like_any_other() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = workflows_declared_on(invalid.NoTransitionWorkflow)

    assert str(raised.value) == (
        'The "transitions" option should have at least 1 element(s) defined.'
    )


def test_a_class_deriving_a_workflow_class_declares_no_workflow() -> None:
    class DerivedTaskWorkflow(declared.TaskWorkflow): ...

    assert workflows_declared_on(DerivedTaskWorkflow) == ()


def test_a_class_without_a_declaration_declares_no_workflow() -> None:
    assert workflows_declared_on(declared.TransitionsBase) == ()


def test_a_function_declares_no_workflow() -> None:
    assert workflows_declared_on(declared.is_user) == ()


def test_an_instance_of_a_workflow_class_declares_no_workflow() -> None:
    assert workflows_declared_on(declared.TaskWorkflow()) == ()
