"""A run that was never started."""

from __future__ import annotations

from typing import final

from .ai_error import AiError

__all__ = ["UnknownRunError"]


@final
class UnknownRunError(AiError, LookupError):
    """A run watched without having been started.

    Attributes:
        run_id: The run asked for.
    """

    run_id: str

    def __init__(self, run_id: str) -> None:
        """Name the run nothing started."""
        self.run_id = run_id
        super().__init__(f'No run "{run_id}" was started; call start() before watch().')
