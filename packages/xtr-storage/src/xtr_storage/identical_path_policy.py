"""What a copy or a move does when source and destination are one path."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["IdenticalPathPolicy"]


class IdenticalPathPolicy(StrEnum):
    """What to do when a copy or a move is asked to go from a path to itself.

    Backends disagree: one rewrites the file with itself, another refuses, a
    third truncates it on the way. The caller decides instead of the backend,
    so the same code behaves the same however the bytes are stored.

    :attr:`IGNORE` is what a call that chose nothing gets, because it is the
    only answer that cannot destroy the file. A move an object store cannot do
    in one step is a copy followed by a delete of the source — and when the two
    paths are one path, the delete removes what the copy just wrote. The two
    other answers stay available to a caller who wants them, named per call or
    per storage.

    The members are their strings, so a configuration carries ``"fail"``.

    Attributes:
        TRY: Hand it to the adapter and live with the backend's answer, whatever
            that is — a rewrite, a refusal, or a file that is no longer there.
        FAIL: Refuse before the backend is touched.
        IGNORE: Return as though it had been done, touching nothing — unless
            there is no file at the path, which is reported as a missing source
            like any other transfer, because nothing was done and no file
            appeared. The default.
    """

    TRY = "try"
    FAIL = "fail"
    IGNORE = "ignore"
