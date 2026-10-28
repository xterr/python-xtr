"""The registrar builds a workflow's definition, checks it, and registers its services."""

from __future__ import annotations

from dataclasses import replace
from enum import StrEnum
from typing import TYPE_CHECKING, cast

import pytest
from xtr_event_dispatcher.bundle import LISTENER_TAG

from tests.fixtures.definition_validator import DefinitionValidator
from tests.support.builds import build_state, definition_of, services_of
from xtr_workflow import Definition, StateMachine, Workflow, WorkflowInterface, WorkflowType
from xtr_workflow.bundle import (
    WORKFLOW_TAG,
    ArcConfig,
    AuditTrailConfig,
    MarkingStoreConfig,
    PlaceConfig,
    TransitionConfig,
    WorkflowDefinitionConfig,
    WorkflowServiceRegistrar,
)
from xtr_workflow.event_listener.guard_listener import GuardListener
from xtr_workflow.exception import InvalidDefinitionError, LogicError
from xtr_workflow.marking_store import MethodMarkingStore
from xtr_workflow.metadata import InMemoryMetadataStore
from xtr_workflow.validator import StateMachineValidator, WorkflowValidator

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection.builder.service_configurator import BuildState

    from xtr_workflow.event_listener import GuardContext, GuardExpression

_ARTICLE_PLACES = (
    "draft",
    "wait_for_journalist",
    "approved_by_journalist",
    "wait_for_spellchecker",
    "approved_by_spellchecker",
    "published",
)


_ARTICLE = WorkflowDefinitionConfig(
    type=WorkflowType.WORKFLOW,
    supports=WorkflowServiceRegistrar,
    initial_marking="draft",
    places=_ARTICLE_PLACES,
    transitions={
        "request_review": TransitionConfig(
            froms="draft", tos=("wait_for_journalist", "wait_for_spellchecker")
        ),
        "journalist_approval": TransitionConfig(
            froms="wait_for_journalist", tos="approved_by_journalist"
        ),
        "spellchecker_approval": TransitionConfig(
            froms="wait_for_spellchecker", tos="approved_by_spellchecker"
        ),
        "publish": TransitionConfig(
            froms=("approved_by_journalist", "approved_by_spellchecker"), tos="published"
        ),
    },
)

_A_TO_B = WorkflowDefinitionConfig(
    supports=WorkflowServiceRegistrar,
    places=("a", "b"),
    transitions={"a_to_b": TransitionConfig(froms="a", tos="b")},
)


def _register(
    name: str,
    config: WorkflowDefinitionConfig,
    *,
    bundles: tuple[str, ...] = (),
) -> tuple[BuildState, WorkflowServiceRegistrar]:
    state = build_state(bundles=bundles)
    registrar = WorkflowServiceRegistrar(frozenset(bundles))
    registrar.register(services_of(state), name, config)
    return state, registrar


def _workflow(state: BuildState, name: str, **arguments: object) -> WorkflowInterface:
    factory = cast(
        "Callable[..., WorkflowInterface]", definition_of(state, WorkflowInterface, name).provider
    )
    return factory(**arguments)


def test_a_workflow_is_registered_tagged_with_what_it_was_registered_from() -> None:
    DefinitionValidator.calls.clear()
    config = replace(
        _ARTICLE,
        definition_validators=(DefinitionValidator,),
        metadata={"title": "article workflow", "description": "workflow for articles"},
    )

    state, _ = _register("article", config)

    workflow = definition_of(state, WorkflowInterface, "article")
    definition = cast("Definition", definition_of(state, Definition, "article").provider)
    assert workflow.get_tag("workflow.workflow") == [{"name": "article"}]
    assert workflow.get_tag(WORKFLOW_TAG) == [
        {
            "name": "article",
            "type": WorkflowType.WORKFLOW,
            "supports": (WorkflowServiceRegistrar,),
            "support_strategy": None,
            "source_class": None,
            "metadata": {"title": "article workflow", "description": "workflow for articles"},
            "definition_validators": (DefinitionValidator, WorkflowValidator),
        }
    ]
    assert DefinitionValidator.calls == [(definition, "article")]
    assert list(definition.get_places()) == list(_ARTICLE_PLACES)
    assert len(definition.get_transitions()) == 4
    assert definition.get_initial_places() == ["draft"]
    metadata_store = definition_of(state, InMemoryMetadataStore, "article").provider
    assert definition.get_metadata_store() is metadata_store
    assert definition.get_metadata_store().get_workflow_metadata() == {
        "title": "article workflow",
        "description": "workflow for articles",
    }


def test_a_state_machine_is_tagged_as_one() -> None:
    state, _ = _register("pull_request", replace(_A_TO_B, metadata={"title": "workflow title"}))

    workflow = definition_of(state, WorkflowInterface, "pull_request")
    assert workflow.get_tag("workflow.state_machine") == [{"name": "pull_request"}]
    assert workflow.get_tag(WORKFLOW_TAG)[0]["definition_validators"] == (StateMachineValidator,)
    assert type(_workflow(state, "pull_request")) is StateMachine


def test_a_workflow_is_validated() -> None:
    config = WorkflowDefinitionConfig(
        supports=WorkflowServiceRegistrar,
        places=("first", "middle", "last"),
        transitions=(
            TransitionConfig("go", froms="first", tos="middle"),
            TransitionConfig("go", froms="first", tos="last"),
        ),
    )

    with pytest.raises(InvalidDefinitionError) as raised:
        _ = _register("my_workflow", config)

    assert str(raised.value) == (
        "A transition from a place/state must have an unique name. Multiple transitions named "
        '"go" from place/state "first" were found on StateMachine "my_workflow".'
    )


def test_a_state_machine_transition_to_several_places_is_one_transition_per_place() -> None:
    config = WorkflowDefinitionConfig(
        supports=WorkflowServiceRegistrar,
        places=("a", "b", "c"),
        transitions={"a_to_b": TransitionConfig(froms="a", tos=("b", "c"))},
    )

    with pytest.raises(InvalidDefinitionError) as raised:
        _ = _register("article", config)

    assert str(raised.value) == (
        "A transition from a place/state must have an unique name. Multiple transitions named "
        '"a_to_b" from place/state "a" were found on StateMachine "article".'
    )


def test_the_marking_store_is_built_on_the_subject_only_when_configured() -> None:
    configured, _ = _register(
        "workflow_a",
        replace(_A_TO_B, marking_store=MarkingStoreConfig(type="method", property="status")),
    )
    default, _ = _register("workflow_b", _A_TO_B)

    store = _workflow(configured, "workflow_a").get_marking_store()
    assert isinstance(store, MethodMarkingStore)
    assert store._single_state
    assert store._marking_property == "status"
    assert isinstance(_workflow(default, "workflow_b").get_marking_store(), MethodMarkingStore)
    assert not definition_of(
        default, WorkflowInterface, "workflow_b"
    ).provider.__annotations__.keys() - {"return"}


def test_a_marking_store_service_is_injected_under_its_qualifier() -> None:
    state, _ = _register(
        "service_marking_store_workflow",
        replace(_A_TO_B, marking_store=MarkingStoreConfig(service="workflow_service")),
    )
    store = MethodMarkingStore()

    workflow = _workflow(state, "service_marking_store_workflow", marking_store=store)

    assert workflow.get_marking_store() is store
    annotations = definition_of(state, WorkflowInterface, "service_marking_store_workflow")
    assert "marking_store" in annotations.provider.__annotations__


def test_the_support_strategy_is_exposed_on_the_tag() -> None:
    config = WorkflowDefinitionConfig(
        type=WorkflowType.WORKFLOW,
        support_strategy="article_support",
        places=("draft", "published"),
        transitions={"publish": TransitionConfig(froms="draft", tos="published")},
    )

    state, _ = _register("article", config)

    tag = definition_of(state, WorkflowInterface, "article").get_tag(WORKFLOW_TAG)[0]
    assert tag["supports"] == ()
    assert tag["support_strategy"] == "article_support"


def test_multiple_transitions_with_the_same_name_keep_their_arcs() -> None:
    config = WorkflowDefinitionConfig(
        type=WorkflowType.WORKFLOW,
        supports=WorkflowServiceRegistrar,
        places=_ARTICLE_PLACES,
        transitions=(
            *_ARTICLE.transitions,
            TransitionConfig("publish", froms="draft", tos=ArcConfig("published", 2)),
        ),
    )

    state, _ = _register("article", config)

    definition = cast("Definition", definition_of(state, Definition, "article").provider)
    assert [
        (
            transition.get_name(),
            [(arc.place, arc.weight) for arc in transition.get_froms(as_arc=True)],
            [(arc.place, arc.weight) for arc in transition.get_tos(as_arc=True)],
        )
        for transition in definition.get_transitions()
    ] == [
        (
            "request_review",
            [("draft", 1)],
            [("wait_for_journalist", 1), ("wait_for_spellchecker", 1)],
        ),
        ("journalist_approval", [("wait_for_journalist", 1)], [("approved_by_journalist", 1)]),
        (
            "spellchecker_approval",
            [("wait_for_spellchecker", 1)],
            [("approved_by_spellchecker", 1)],
        ),
        (
            "publish",
            [("approved_by_journalist", 1), ("approved_by_spellchecker", 1)],
            [("published", 1)],
        ),
        ("publish", [("draft", 1)], [("published", 2)]),
    ]


class _Places(StrEnum):
    A = "a"
    B = "b"
    C = "c"


def test_places_may_be_the_members_of_an_enum() -> None:
    config = WorkflowDefinitionConfig(
        supports=WorkflowServiceRegistrar,
        places=tuple(_Places),
        transitions={
            "one": TransitionConfig(froms=_Places.A, tos=_Places.B),
            "two": TransitionConfig(froms=_Places.B, tos=_Places.C),
        },
    )

    state, _ = _register("enum", config)

    definition = cast("Definition", definition_of(state, Definition, "enum").provider)
    assert list(definition.get_places()) == ["a", "b", "c"]
    assert [(t.get_froms(), t.get_tos()) for t in definition.get_transitions()] == [
        (["a"], ["b"]),
        (["b"], ["c"]),
    ]


def _allowed(_context: GuardContext) -> bool:
    return True


def _refused(_context: GuardContext) -> bool:
    return False


def test_guards_are_run_by_a_guard_listener_for_the_unit_of_work() -> None:
    config = WorkflowDefinitionConfig(
        type=WorkflowType.WORKFLOW,
        supports=WorkflowServiceRegistrar,
        places=_ARTICLE_PLACES,
        transitions=(
            *_ARTICLE.transitions[:3],
            TransitionConfig(
                "publish",
                froms=("approved_by_journalist", "approved_by_spellchecker"),
                tos="published",
                guard=_allowed,
            ),
            TransitionConfig("publish", froms="draft", tos="published", guard=_refused),
        ),
    )

    state, _ = _register("article", config, bundles=("security",))

    definition = cast("Definition", definition_of(state, Definition, "article").provider)
    guard_listener = definition_of(state, GuardListener, "article")
    [guards] = guard_listener.get_arguments().values()
    [expressions] = cast("dict[str, list[GuardExpression]]", guards).values()
    transitions = definition.get_transitions()
    assert guard_listener.lifetime == "scoped"
    assert list(cast("dict[str, object]", guards)) == ["workflow.article.guard.publish"]
    assert [(e.get_transition(), e.get_expression()) for e in expressions] == [
        (transitions[3], _allowed),
        (transitions[4], _refused),
    ]
    [listener] = [
        definition
        for definition in state.store.entries()
        if definition.key[1] == "article" and definition.has_tag(LISTENER_TAG)
    ]
    assert listener.get_tag(LISTENER_TAG) == [
        {"event": "workflow.article.guard.publish", "method": "on_transition"}
    ]


def test_guards_need_the_security_bundle() -> None:
    config = WorkflowDefinitionConfig(
        places=("a", "b"),
        transitions={"go": TransitionConfig(froms="a", tos="b", guard=_allowed)},
    )

    with pytest.raises(LogicError) as raised:
        _ = _register("article", config)

    assert str(raised.value) == (
        'The "security" bundle is needed to be able to use the workflow guard listener.'
    )


def test_an_audit_trail_listens_to_its_workflow_only() -> None:
    state, _ = _register(
        "article",
        replace(_A_TO_B, audit_trail=AuditTrailConfig(enabled=True)),
        bundles=("event_dispatcher", "logging"),
    )

    [listener] = [
        definition
        for definition in state.store.entries()
        if definition.key[1] == "article" and definition.has_tag(LISTENER_TAG)
    ]
    assert listener.get_tag(LISTENER_TAG) == [
        {"event": "workflow.article.leave", "method": "on_leave"},
        {"event": "workflow.article.transition", "method": "on_transition"},
        {"event": "workflow.article.enter", "method": "on_enter"},
    ]


@pytest.mark.parametrize(
    ("active", "missing"), [(("logging",), "event_dispatcher"), (("event_dispatcher",), "logging")]
)
def test_an_audit_trail_needs_the_event_dispatcher_and_logging(
    active: tuple[str, ...], missing: str
) -> None:
    with pytest.raises(LogicError) as raised:
        _ = _register(
            "article", replace(_A_TO_B, audit_trail=AuditTrailConfig(enabled=True)), bundles=active
        )

    assert str(raised.value) == (
        f'The "{missing}" bundle is needed to be able to use the audit trail of the "article" '
        "workflow."
    )


@pytest.mark.parametrize(
    ("events_to_dispatch", "expected"),
    [
        ((), frozenset[str]()),
        (
            ("workflow.leave", "workflow.completed"),
            frozenset({"workflow.leave", "workflow.completed"}),
        ),
    ],
)
def test_the_events_to_dispatch_are_handed_to_the_workflow(
    events_to_dispatch: tuple[str, ...], expected: frozenset[str]
) -> None:
    state, _ = _register("my_workflow", replace(_A_TO_B, events_to_dispatch=events_to_dispatch))

    workflow = cast("Workflow", _workflow(state, "my_workflow"))

    assert workflow._events_to_dispatch == expected


def test_without_a_dispatcher_bundle_the_workflow_dispatches_nothing() -> None:
    state, _ = _register("my_workflow", _A_TO_B)

    workflow = cast("Workflow", _workflow(state, "my_workflow"))

    assert workflow._dispatcher is None


def test_places_metadata_is_kept_only_for_places_having_some() -> None:
    config = WorkflowDefinitionConfig(
        places=(PlaceConfig("a", {"title": "A"}), PlaceConfig("b")),
        transitions={"go": TransitionConfig(froms="a", tos="b")},
    )

    state, _ = _register("my_workflow", config)

    store = cast(
        "InMemoryMetadataStore", definition_of(state, InMemoryMetadataStore, "my_workflow").provider
    )
    assert store._places_metadata == {"a": {"title": "A"}}


def test_a_class_cannot_take_the_name_of_a_configured_workflow() -> None:
    state, registrar = _register("task", _A_TO_B)

    with pytest.raises(LogicError) as raised:
        registrar.register(services_of(state), "task", _A_TO_B, DefinitionValidator)

    assert str(raised.value) == (
        'The workflow "task" defined by "tests.fixtures.definition_validator.DefinitionValidator" '
        "is already defined by the configuration."
    )
