from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_cli import Scaffolder, command_support

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import pytest

__all__ = ["RecordingRunner", "record_processes"]


@final
class RecordingRunner:
    """Answers each command with a prepared code, and remembers what it was asked to run."""

    def __init__(self, codes: Sequence[int] = ()) -> None:
        self.calls: list[tuple[tuple[str, ...], Path]] = []
        self._codes = tuple(codes)

    def run(self, argv: Sequence[str], cwd: Path) -> int:
        """Record one call; answer with the code prepared for it, or success."""
        self.calls.append((tuple(argv), cwd))
        index = len(self.calls) - 1
        return self._codes[index] if index < len(self._codes) else 0


def record_processes(monkeypatch: pytest.MonkeyPatch, *codes: int) -> RecordingRunner:
    """Make every command scaffold through a recorder pinned to version 3.0.0."""
    runner = RecordingRunner(codes)

    def build() -> Scaffolder:
        return Scaffolder(runner, "3.0.0")

    monkeypatch.setattr(command_support, "build_scaffolder", build)
    return runner
