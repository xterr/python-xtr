"""``ai:run:cancel``: ask a run to stop, wherever it runs."""

from __future__ import annotations

from typing import final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape

from xtr_ai.run_control_interface import RunControlInterface

from ._registry import AI_COMMANDS

__all__ = ["RunCancelCommand"]


@as_command("ai:run:cancel", registry=AI_COMMANDS)
@final
class RunCancelCommand:
    """Ask a running agent run to stop; the process running it stops it at its next check."""

    __slots__ = ("_run_control",)

    def __init__(self, run_control: RunControlInterface) -> None:
        """Flag runs through ``run_control``."""
        self._run_control = run_control

    async def __call__(self, io: ConsoleStyle, run_id: str) -> int:
        """Flag ``run_id`` for cancellation.

        Args:
            io: Where the command writes.
            run_id: The run to stop.
        """
        if await self._run_control.request_cancel(run_id):
            io.success(f"Cancellation of {escape(run_id)} requested.")
            return ExitCode.SUCCESS
        io.warning(f"No run {escape(run_id)} is in progress.")
        return ExitCode.FAILURE
