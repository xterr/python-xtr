"""SubprocessRunner: the commands that finish a project, run as real processes."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = ["NOT_FOUND", "SubprocessRunner"]

NOT_FOUND: Final = 127
"""The code a command that is not on the ``PATH`` ends with, as a shell reports it."""


@final
class SubprocessRunner:
    """Starts each command as a child process, attached to this one's terminal.

    ``VIRTUAL_ENV`` is left out of the child's environment: the new project
    always works in its own ``.venv``, and an environment active in the shell
    — the one this tool runs from, say — would only make ``uv`` warn that it
    is being ignored.
    """

    __slots__ = ()

    def run(self, argv: Sequence[str], cwd: Path) -> int:
        """Run ``argv`` in ``cwd`` and return its exit code; ``127`` when it is not found."""
        environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
        try:
            completed = subprocess.run(  # noqa: S603 — argv is built by the scaffolder.
                list(argv), cwd=cwd, env=environment, check=False
            )
        except FileNotFoundError:
            return NOT_FOUND
        return completed.returncode
