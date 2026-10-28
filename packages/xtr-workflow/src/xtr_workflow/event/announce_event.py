"""A transition is enabled now that the subject has moved."""

from __future__ import annotations

from typing import final

from ._event_name import event_name
from ._has_context import HasContextTrait

__all__ = ["AnnounceEvent"]


@final
class AnnounceEvent(HasContextTrait):
    """A transition is enabled for the subject, now that a transition has moved it.

    Announced once per transition enabled after the move, so a listener can
    chain the next step.
    """

    @staticmethod
    def get_name(workflow_name: str | None = None, node: str | None = None) -> str:
        """Return the name this event goes out under, narrowed to a workflow and a transition.

        Raises:
            InvalidArgumentError: If a transition is named without its workflow.
        """
        return event_name(AnnounceEvent, workflow_name, node)
