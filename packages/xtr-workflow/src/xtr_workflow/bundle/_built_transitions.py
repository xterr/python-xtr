"""The transitions of a configured workflow, built, with the guards and the metadata set on them."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, assert_never

from xtr_workflow.arc import Arc
from xtr_workflow.event_listener import GuardExpression
from xtr_workflow.transition import Transition
from xtr_workflow.workflow_type import WorkflowType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .workflow_definition_config import WorkflowDefinitionConfig

__all__ = ["BuiltTransitions", "built_transitions"]


class BuiltTransitions(NamedTuple):
    """The transitions of a definition, with the guards and the metadata set on them."""

    transitions: list[Transition]
    """Every transition, in the order configured."""

    guards: dict[str, list[GuardExpression]]
    """The guards, by the name of the guard event they run for."""

    metadata: dict[Transition, Mapping[str, object]]
    """The metadata of each transition having some."""


def built_transitions(name: str, config: WorkflowDefinitionConfig) -> BuiltTransitions:
    """Build the transitions of the workflow ``name``: one per entry, or per pair of places.

    A state machine's subject moves from one place to one place, so an entry
    of a state machine leaving or entering several places is one transition
    for each pair of places it joins, each guarded and described as the
    entry is.
    """
    built = BuiltTransitions([], {}, {})
    for transition in config.transitions:
        froms = [Arc(arc.place, arc.weight) for arc in transition.froms]
        tos = [Arc(arc.place, arc.weight) for arc in transition.tos]
        match config.type:
            case WorkflowType.WORKFLOW:
                pairs = [(froms, tos)]
            case WorkflowType.STATE_MACHINE:
                pairs = [([arc_from], [arc_to]) for arc_from in froms for arc_to in tos]
            case _:
                assert_never(config.type)
        for arcs_from, arcs_to in pairs:
            built_transition = Transition(transition.name, arcs_from, arcs_to)
            built.transitions.append(built_transition)
            if transition.guard is not None:
                event_name = f"workflow.{name}.guard.{transition.name}"
                guard = GuardExpression(built_transition, transition.guard)
                built.guards.setdefault(event_name, []).append(guard)
            if transition.metadata:
                built.metadata[built_transition] = transition.metadata
    return built
