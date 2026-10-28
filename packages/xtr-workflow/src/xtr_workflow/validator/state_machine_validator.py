"""Checking that a definition can run as a state machine."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_workflow.exception import InvalidDefinitionError

from .definition_validator_interface import DefinitionValidatorInterface

if TYPE_CHECKING:
    from xtr_workflow.definition import Definition
    from xtr_workflow.transition import Transition

__all__ = ["StateMachineValidator"]


@final
class StateMachineValidator(DefinitionValidatorInterface):
    """Checks that a definition can run as a state machine.

    A state machine's subject is in one place at a time, so every transition
    must take it from exactly one place to exactly one place, one token at a
    time, and the definition can start it in one place at most.

    Transitions may share a name — a state machine needs one for each pair of
    places a move joins — but no two of them may leave the same place:
    applying that name there could take the subject to either.
    """

    __slots__ = ()

    @override
    def validate(self, definition: Definition, name: str) -> None:
        """Refuse ``definition`` unless it can run as the state machine ``name``.

        Args:
            definition: The definition to check.
            name: The name of the state machine, quoted in the error.

        Raises:
            InvalidDefinitionError: If a transition does not move one token
                from one place to one place, if two transitions of one name
                leave the same place, or if the definition starts a subject in
                several places.
        """
        names_leaving: defaultdict[str, set[str]] = defaultdict(set)
        for transition in definition.get_transitions():
            _check_moves_one_token(transition, name)
            [place] = transition.get_froms()
            transition_name = transition.get_name()
            if transition_name in names_leaving[place]:
                raise InvalidDefinitionError(
                    "A transition from a place/state must have an unique name. Multiple "
                    f'transitions named "{transition_name}" from place/state "{place}" were '
                    f'found on StateMachine "{name}".'
                )
            names_leaving[place].add(transition_name)

        initial_places = definition.get_initial_places()
        if len(initial_places) > 1:
            raise InvalidDefinitionError(
                f'The state machine "{name}" cannot store many places. But the definition has '
                f"{len(initial_places)} initial places. Only one is supported."
            )


def _check_moves_one_token(transition: Transition, state_machine_name: str) -> None:
    """Refuse ``transition`` unless it moves one token from one place to one place.

    Raises:
        InvalidDefinitionError: If ``transition`` has other than one output or
            one input, or an arc weighing more than one token.
    """
    transition_name = transition.get_name()
    tos = transition.get_tos(as_arc=True)
    if len(tos) != 1:
        raise InvalidDefinitionError(
            "A transition in StateMachine can only have one output. But the transition "
            f'"{transition_name}" in StateMachine "{state_machine_name}" has {len(tos)} outputs.'
        )
    froms = transition.get_froms(as_arc=True)
    for arc_in in froms:
        if arc_in.weight > 1:
            raise InvalidDefinitionError(
                "A transition in StateMachine can only have arc with weight equals to one. But "
                f'the transition "{transition_name}" in StateMachine "{state_machine_name}" has '
                f'an arc from "{arc_in.place}" to the transition with a weight equals to '
                f"{arc_in.weight}."
            )
    if len(froms) != 1:
        raise InvalidDefinitionError(
            "A transition in StateMachine can only have one input. But the transition "
            f'"{transition_name}" in StateMachine "{state_machine_name}" has {len(froms)} inputs.'
        )
    [arc_out] = tos
    if arc_out.weight > 1:
        raise InvalidDefinitionError(
            "A transition in StateMachine can only have arc with weight equals to one. But "
            f'the transition "{transition_name}" in StateMachine "{state_machine_name}" has '
            f'an arc from the transition to "{arc_out.place}" with a weight equals to '
            f"{arc_out.weight}."
        )
