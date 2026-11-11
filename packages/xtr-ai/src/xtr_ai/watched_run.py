"""The handle ``watch`` gives the code running an agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from pydantic_ai.usage import RunUsage

__all__ = ["WatchedRun"]


@final
class WatchedRun:
    """A run being watched: where its usage is handed over before the watch ends.

    ```python
    async with run_control.watch(run_id, token) as watched:
        result = await agent.run(prompt, cancellation_token=token)
        watched.record_usage(result.usage)
    ```
    """

    __slots__ = ("_usage", "run_id")

    def __init__(self, run_id: str) -> None:
        """Watch ``run_id``; no usage recorded yet."""
        self.run_id = run_id
        self._usage: RunUsage | None = None

    @property
    def usage(self) -> RunUsage | None:
        """The usage recorded so far, if any."""
        return self._usage

    def record_usage(self, usage: RunUsage) -> None:
        """Keep ``usage`` to store with the run's terminal state."""
        self._usage = usage
