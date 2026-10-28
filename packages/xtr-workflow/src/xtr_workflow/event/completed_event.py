"""A transition has been applied."""

from __future__ import annotations

from typing import final

from ._event_name import event_name
from ._has_context import HasContextTrait

__all__ = ["CompletedEvent"]


@final
class CompletedEvent(HasContextTrait):
    """A transition has been applied in full: the subject is in its new places, recorded."""

    @staticmethod
    def get_name(workflow_name: str | None = None, node: str | None = None) -> str:
        """Return the name this event goes out under, narrowed to a workflow and a transition.

        Raises:
            InvalidArgumentError: If a transition is named without its workflow.
        """
        return event_name(CompletedEvent, workflow_name, node)
