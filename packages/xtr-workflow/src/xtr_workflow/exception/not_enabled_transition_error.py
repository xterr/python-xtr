"""A transition is defined, but blocked for the subject."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .transition_error import TransitionError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .transition_error import NamedWorkflow

__all__ = ["NotEnabledTransitionError"]


class NotEnabledTransitionError(TransitionError):
    """A transition is defined, but its blockers keep it from being applied to the subject.

    The marking may lack the tokens the transition takes, or a guard may have
    refused it; the blocker list it carries says which, and why.
    """

    _transition_blocker_list: object

    def __init__(
        self,
        subject: object,
        transition_name: str,
        workflow: NamedWorkflow,
        transition_blocker_list: object,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Record the blocked call and what blocks it.

        Args:
            subject: The object the transition was to move.
            transition_name: The name of the transition.
            workflow: The workflow the transition was applied through.
            transition_blocker_list: What blocks the transition.
            context: The context the call was given.
        """
        super().__init__(
            subject,
            transition_name,
            workflow,
            f'Cannot apply transition "{transition_name}" on workflow "{workflow.get_name()}".',
            context,
        )
        self._transition_blocker_list = transition_blocker_list

    def get_transition_blocker_list(self) -> object:
        """Return what blocks the transition."""
        return self._transition_blocker_list
