"""Collecting the failed cases of one check, to report them together."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["raise_failures"]


def raise_failures(subject: str, failures: Sequence[str]) -> None:
    """Raise one :class:`AssertionError` listing every failure, or nothing when there is none.

    Every case is checked before anything is raised, so one run shows all a
    provider gets wrong instead of the first of it.
    """
    if failures:
        listed = "\n".join(f"- {failure}" for failure in failures)
        raise AssertionError(f"The {subject} fails {len(failures)} case(s):\n{listed}")
