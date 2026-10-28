"""The steps of a task, each valued with the name of the place it stands for."""

from __future__ import annotations

from enum import StrEnum


class TaskStep(StrEnum):
    NEW = "new"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
