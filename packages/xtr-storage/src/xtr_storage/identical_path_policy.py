"""What a copy or a move does when source and destination are one path."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["IdenticalPathPolicy"]


class IdenticalPathPolicy(StrEnum):
    """What to do when a copy or a move is asked to go from a path to itself.

    Backends disagree: one rewrites the file with itself, another refuses, a
    third truncates it on the way. The caller decides instead of the backend,
    so the same code behaves the same however the bytes are stored.

    The members are their strings, so a configuration carries ``"fail"``.

    Attributes:
        TRY: Hand it to the adapter and live with the backend's answer.
        FAIL: Refuse before the backend is touched.
        IGNORE: Return as though it had been done, touching nothing.
    """

    TRY = "try"
    FAIL = "fail"
    IGNORE = "ignore"
