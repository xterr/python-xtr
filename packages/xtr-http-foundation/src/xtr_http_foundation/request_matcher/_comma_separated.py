"""Reading one name, or several, out of what a matcher was given."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["comma_separated"]

_SEPARATOR: Final = re.compile(r"\s*,\s*")


def comma_separated(given: Sequence[str] | str) -> tuple[str, ...]:
    """Return every name ``given`` holds, however they were written.

    A matcher takes one name or a list of them, and each of those may itself
    hold several separated by commas — so a name read from configuration, where
    a list is awkward to write, reaches the matcher the same way a list does.
    Whitespace around a comma belongs to the separator rather than to a name.

    Args:
        given: One name, or several; any of them may be a comma-separated list.

    Returns:
        The names, in the order they were written.
    """
    values = (given,) if isinstance(given, str) else given

    return tuple(name for value in values for name in _SEPARATOR.split(value))
