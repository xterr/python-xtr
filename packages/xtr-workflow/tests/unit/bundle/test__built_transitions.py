"""A workflow's entries become transitions; a state machine's, one per pair of places."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_workflow import WorkflowType
from xtr_workflow.bundle import TransitionConfig, WorkflowDefinitionConfig
from xtr_workflow.bundle._built_transitions import built_transitions

if TYPE_CHECKING:
    from xtr_workflow.event_listener import GuardContext


def _guard(_context: GuardContext) -> bool:
    return True


def _config(workflow_type: WorkflowType) -> WorkflowDefinitionConfig:
    return WorkflowDefinitionConfig(
        type=workflow_type,
        transitions=(
            TransitionConfig(
                "go", froms=("a", "b"), tos=("c", "d"), guard=_guard, metadata={"title": "Go"}
            ),
        ),
    )


def test_a_workflow_entry_is_one_transition() -> None:
    built = built_transitions("flow", _config(WorkflowType.WORKFLOW))

    [transition] = built.transitions
    assert (transition.get_froms(), transition.get_tos()) == (["a", "b"], ["c", "d"])
    assert built.metadata == {transition: {"title": "Go"}}


def test_a_state_machine_entry_is_one_transition_per_pair_of_places() -> None:
    built = built_transitions("machine", _config(WorkflowType.STATE_MACHINE))

    assert [(t.get_froms(), t.get_tos()) for t in built.transitions] == [
        (["a"], ["c"]),
        (["a"], ["d"]),
        (["b"], ["c"]),
        (["b"], ["d"]),
    ]
    [guards] = built.guards.values()
    assert list(built.guards) == ["workflow.machine.guard.go"]
    assert [guard.get_transition() for guard in guards] == built.transitions
    assert all(guard.get_expression() is _guard for guard in guards)
    assert list(built.metadata) == built.transitions
