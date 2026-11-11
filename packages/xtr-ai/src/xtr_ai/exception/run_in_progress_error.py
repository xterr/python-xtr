"""A second top-level run started on a conversation that already has one running."""

from __future__ import annotations

from typing import final

from .ai_error import AiError

__all__ = ["RunInProgressError"]


@final
class RunInProgressError(AiError):
    """A conversation already has a top-level run in progress.

    Attributes:
        conversation_id: The conversation that is busy.
        running_run_id: The run that holds it, when the backend can tell.
    """

    conversation_id: str
    running_run_id: str | None

    def __init__(self, conversation_id: str, running_run_id: str | None = None) -> None:
        """Name the busy conversation, and the run holding it when known."""
        self.conversation_id = conversation_id
        self.running_run_id = running_run_id
        holder = f' by run "{running_run_id}"' if running_run_id is not None else ""
        super().__init__(
            f'The conversation "{conversation_id}" already has a run in progress{holder}; '
            "wait for it to end or cancel it.",
        )
