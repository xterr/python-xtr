"""What the commands run ``uv``, ``git`` and an application's server through."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

__all__ = ["ProcessRunnerInterface"]


@runtime_checkable
class ProcessRunnerInterface(Protocol):
    """Runs one command to completion and reports how it ended.

    Structural on purpose: the default starts a real process, while a test
    supplies a recorder, so a project can be planned and written without
    installing anything.
    """

    def run(self, argv: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None) -> int:
        """Run ``argv`` in ``cwd``, its output going straight to the terminal; return its code.

        ``env`` holds variables set for the command on top of this process's
        own environment.
        """
        ...
