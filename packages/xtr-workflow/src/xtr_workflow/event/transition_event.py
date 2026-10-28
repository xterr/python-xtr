"""A transition is being applied, between leaving its places and entering the next."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from ._event_name import event_name
from ._has_context import HasContextTrait

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["TransitionEvent"]


@final
class TransitionEvent(HasContextTrait):
    """A transition is being applied: the subject has left its places and not entered the next.

    The one moment a listener may replace the call's context; the context it
    sets is what the later events and the marking store receive.
    """

    @staticmethod
    def get_name(workflow_name: str | None = None, node: str | None = None) -> str:
        """Return the name this event goes out under, narrowed to a workflow and a transition.

        Raises:
            InvalidArgumentError: If a transition is named without its workflow.
        """
        return event_name(TransitionEvent, workflow_name, node)

    def set_context(self, context: Mapping[str, object]) -> None:
        """Replace the context the rest of the transition runs with."""
        self._context = dict(context)
