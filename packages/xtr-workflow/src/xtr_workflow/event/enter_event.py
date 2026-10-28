"""The subject is entering a place."""

from __future__ import annotations

from typing import final

from ._event_name import event_name
from ._has_context import HasContextTrait

__all__ = ["EnterEvent"]


@final
class EnterEvent(HasContextTrait):
    """The subject is entering the places a transition takes it to; no token is there yet."""

    @staticmethod
    def get_name(workflow_name: str | None = None, node: str | None = None) -> str:
        """Return the name this event goes out under, narrowed to a workflow and a place.

        Raises:
            InvalidArgumentError: If a place is named without its workflow.
        """
        return event_name(EnterEvent, workflow_name, node)
