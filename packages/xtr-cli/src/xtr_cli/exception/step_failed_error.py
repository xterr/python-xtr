"""A command the scaffold runs — ``uv`` or ``git`` — that exited with a failure."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .cli_error import CliError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["StepFailedError"]


@final
class StepFailedError(CliError):
    """One of the commands that finish a project failed; the rest were not run.

    The command has already said why on its own streams. What it left behind is
    kept: the files written so far are the project, and running the remaining
    commands by hand — or deleting the directory — is the way on.

    Attributes:
        argv: The command that failed, program and all.
        cwd: Where it ran.
        code: The exit code it ended with.
    """

    argv: tuple[str, ...]
    cwd: Path
    code: int

    def __init__(self, argv: tuple[str, ...], cwd: Path, code: int) -> None:
        """Record the command, where it ran, and how it ended."""
        self.argv = argv
        self.cwd = cwd
        self.code = code
        super().__init__(f"`{' '.join(argv)}` exited with {code} in {cwd}")
