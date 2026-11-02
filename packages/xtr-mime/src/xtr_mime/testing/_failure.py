"""The one way every check reports a failed expectation."""

from __future__ import annotations

from typing import NoReturn

__all__ = ["fail"]


def fail(expectation: str) -> NoReturn:
    """Raise an :class:`AssertionError` saying ``expectation`` did not hold.

    Raises:
        AssertionError: Always.
    """
    raise AssertionError(f"Failed asserting that {expectation}.")
