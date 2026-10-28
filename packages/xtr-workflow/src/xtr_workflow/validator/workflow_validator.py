"""Checking that a definition can run as a workflow."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_workflow.exception import InvalidDefinitionError

from .definition_validator_interface import DefinitionValidatorInterface

if TYPE_CHECKING:
    from xtr_workflow.definition import Definition
    from xtr_workflow.transition import Transition

__all__ = ["WorkflowValidator"]


@final
class WorkflowValidator(DefinitionValidatorInterface):
    """Checks that a definition can run as a workflow.

    Applying a name fires every enabled transition of that name, so no two
    transitions of one name may leave the same place: both would take its
    tokens.

    A marking store keeping a single place per subject — a place name, as a
    state machine's store does — cannot record a subject in two places, nor
    two tokens in one. Built with ``single_place`` for a workflow whose store
    is one, the validator also refuses a transition putting tokens in several
    places, an arc moving several tokens, and several initial places.
    """

    __slots__ = ("_single_place",)

    _single_place: bool

    def __init__(self, single_place: bool = False) -> None:
        """Check definitions for a workflow, and for a single place when ``single_place``.

        Args:
            single_place: Also refuse what a marking store keeping a single
                place per subject cannot record — off by default, as a
                workflow's store keeps every place its subject is in.
        """
        self._single_place = single_place

    @override
    def validate(self, definition: Definition, name: str) -> None:
        """Refuse ``definition`` unless it can run as the workflow ``name``.

        Args:
            definition: The definition to check.
            name: The name of the workflow, quoted in the error.

        Raises:
            InvalidDefinitionError: If two transitions of one name leave the
                same place; with ``single_place``, also if a transition puts
                tokens in several places or moves several tokens through an
                arc, or if the definition starts a subject in several places.
        """
        names_leaving: defaultdict[str, set[str]] = defaultdict(set)
        for transition in definition.get_transitions():
            transition_name = transition.get_name()
            for place in transition.get_froms():
                if transition_name in names_leaving[place]:
                    raise InvalidDefinitionError(
                        "All transitions for a place must have an unique name. Multiple "
                        f'transitions named "{transition_name}" where found for place "{place}" '
                        f'in workflow "{name}".'
                    )
                names_leaving[place].add(transition_name)

        if not self._single_place:
            return

        for transition in definition.get_transitions():
            _check_fits_a_single_place(transition, name)

        initial_places = definition.get_initial_places()
        if len(initial_places) > 1:
            raise InvalidDefinitionError(
                f'The marking store of workflow "{name}" cannot store many places. But the '
                f"definition has {len(initial_places)} initial places. Only one is supported."
            )


def _check_fits_a_single_place(transition: Transition, workflow_name: str) -> None:
    """Refuse ``transition`` unless a marking store keeping a single place can record its move.

    Raises:
        InvalidDefinitionError: If ``transition`` puts tokens in several
            places, or moves several tokens through one of its arcs.
    """
    transition_name = transition.get_name()
    tos = transition.get_tos(as_arc=True)
    if len(tos) > 1:
        raise InvalidDefinitionError(
            f'The marking store of workflow "{workflow_name}" cannot store many places. But the '
            f'transition "{transition_name}" has too many output ({len(tos)}). Only one is '
            "accepted."
        )
    for arc in transition.get_froms(as_arc=True):
        if arc.weight > 1:
            raise InvalidDefinitionError(
                f'The marking store of workflow "{workflow_name}" cannot store many places. But '
                f'the transition "{transition_name}" has an arc from place "{arc.place}" with a '
                f"weight of {arc.weight}."
            )
    for arc in tos:
        if arc.weight > 1:
            raise InvalidDefinitionError(
                f'The marking store of workflow "{workflow_name}" cannot store many places. But '
                f'the transition "{transition_name}" has an arc to place "{arc.place}" with a '
                f"weight of {arc.weight}."
            )
