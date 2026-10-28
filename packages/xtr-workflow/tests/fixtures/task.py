"""A task keeping its step in a plain attribute, with what its listeners leave on it."""

from __future__ import annotations

from typing import final

from tests.fixtures.task_step import TaskStep


@final
class Task:
    # Declared on the class, where the marking store reads that the step is an enum.
    step: TaskStep

    def __init__(self) -> None:
        self.step = TaskStep.NEW
        self.blocked = False
        self.context: dict[str, object] = {}
