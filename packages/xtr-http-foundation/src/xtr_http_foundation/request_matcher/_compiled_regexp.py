"""Reading a matcher's regular expression once, where it is given."""

from __future__ import annotations

import re

from xtr_http_foundation.exception import InvalidArgumentError

__all__ = ["compiled_regexp"]


def compiled_regexp(regexp: str, flags: int = 0) -> re.Pattern[str]:
    """Return ``regexp`` read as a pattern, refusing it where it is written.

    A matcher is built once and asked on every request, so the expression is
    read when the matcher is built: the cost is paid once, and an expression
    nobody can read fails where it was written rather than on the first request
    that happens to reach it.

    Args:
        regexp: The expression, unanchored — a matcher searches the value it is
            about rather than requiring the whole of it to match.
        flags: How to read it.

    Returns:
        The compiled pattern.

    Raises:
        InvalidArgumentError: When the expression does not read as one. It names
            the expression, since a matcher holds no other clue to which it was.
    """
    try:
        return re.compile(regexp, flags)
    except re.error as error:
        raise InvalidArgumentError(
            f'"{regexp}" is not a valid regular expression: {error}'
        ) from error
