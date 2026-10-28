"""In debug mode, every workflow is wrapped in a traceable one."""

from __future__ import annotations

from tests.support.builds import build_state, builder_of, definition_of, services_of
from xtr_workflow import WorkflowInterface
from xtr_workflow.bundle import (
    WORKFLOW_TAG,
    TransitionConfig,
    WorkflowDebugPass,
    WorkflowDefinitionConfig,
    WorkflowServiceRegistrar,
)
from xtr_workflow.debug import TraceableWorkflow


def test_every_tagged_workflow_is_decorated_by_a_resettable_traceable_one() -> None:
    state = build_state(debug=True)
    WorkflowServiceRegistrar().register(
        services_of(state),
        "article",
        WorkflowDefinitionConfig(transitions={"go": TransitionConfig(froms="a", tos="b")}),
    )

    WorkflowDebugPass().process(builder_of(state))

    traceable = definition_of(state, TraceableWorkflow, "article")
    decorates = traceable.decorates
    assert decorates is not None
    assert decorates.key == (WorkflowInterface, "article")
    assert traceable.get_tag("kernel.reset") == [{"method": "reset"}]


def test_a_service_tagged_by_hand_is_decorated_too() -> None:
    state = build_state(debug=True)
    _ = services_of(state).set(TraceableWorkflow, qualifier="by_hand").add_tag(WORKFLOW_TAG)

    WorkflowDebugPass().process(builder_of(state))

    assert state.store.get((TraceableWorkflow, "by_hand")) is not None
    decorates = definition_of(state, TraceableWorkflow, "by_hand").decorates
    assert decorates is not None
    assert decorates.key == (TraceableWorkflow, "by_hand")


def test_nothing_is_decorated_without_a_workflow() -> None:
    state = build_state(debug=True)

    WorkflowDebugPass().process(builder_of(state))

    assert state.store.entries() == ()
