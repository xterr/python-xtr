"""SubprocessRunner: the commands this tool runs, as real processes."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
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

    Ctrl-C reaches the child as well as this process, since both share the
    terminal. The child is then waited for rather than killed, so a server
    finishes shutting down — its application's shutdown hooks included — before
    this process ends; a second Ctrl-C stops waiting.
    """

    __slots__ = ()

    def run(self, argv: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None) -> int:
        """Run ``argv`` in ``cwd`` and return its exit code; ``127`` when it is not found."""
        environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
        environment.update(env or {})
        try:
            process = subprocess.Popen(list(argv), cwd=cwd, env=environment)  # noqa: S603 — argv is built by a command.
        except FileNotFoundError:
            return NOT_FOUND
        try:
            return process.wait()
        except KeyboardInterrupt:
            return process.wait()
