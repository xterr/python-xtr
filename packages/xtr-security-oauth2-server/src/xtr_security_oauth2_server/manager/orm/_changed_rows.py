"""How many rows a statement changed, as the driver reported it."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from sqlalchemy import CursorResult

__all__ = ["changed_rows"]


def changed_rows(result: object, /) -> int:
    """Return how many rows a statement changed.

    Running a statement through a session is typed as handing back a plain
    result, while what a change really answers with is the cursor's, which is
    where the driver's count is. Only the result of a change is passed here.
    """
    return cast("CursorResult[object]", result).rowcount
