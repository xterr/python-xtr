"""A transition was applied that the workflow does not define."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .transition_error import TransitionError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .transition_error import NamedWorkflow

__all__ = ["UndefinedTransitionError"]


class UndefinedTransitionError(TransitionError):
    """A transition was applied that the workflow's definition does not have."""

    def __init__(
        self,
        subject: object,
        transition_name: str,
        workflow: NamedWorkflow,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Record the call naming a transition the definition does not have.

        Args:
            subject: The object the transition was to move.
            transition_name: The name no transition of the definition has.
            workflow: The workflow the transition was applied through.
            context: The context the call was given.
        """
        super().__init__(
            subject,
            transition_name,
            workflow,
            f'Transition "{transition_name}" is not defined for workflow "{workflow.get_name()}".',
            context,
        )
