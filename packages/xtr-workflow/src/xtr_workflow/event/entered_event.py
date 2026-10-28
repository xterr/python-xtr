"""The subject has entered a place."""

from __future__ import annotations

from typing import final

from ._event_name import event_name
from ._has_context import HasContextTrait

__all__ = ["EnteredEvent"]


@final
class EnteredEvent(HasContextTrait):
    """The subject has entered its new places, and the marking store has recorded them.

    Also announced when a subject is given its initial marking, with no
    transition.
    """

    @staticmethod
    def get_name(workflow_name: str | None = None, node: str | None = None) -> str:
        """Return the name this event goes out under, narrowed to a workflow and a place.

        Raises:
            InvalidArgumentError: If a place is named without its workflow.
        """
        return event_name(EnteredEvent, workflow_name, node)
