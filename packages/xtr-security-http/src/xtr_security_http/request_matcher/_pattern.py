"""Compile a request matcher's regular expression, naming a bad one where written."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from re import Pattern

__all__ = ["compile_pattern"]


def compile_pattern(pattern: str, field_name: str) -> Pattern[str]:
    """Compile ``pattern``, naming ``field_name`` when it will not compile.

    Raises:
        InvalidArgumentError: When ``pattern`` is not a valid regular expression.
    """
    try:
        return re.compile(pattern)
    except re.error as error:
        raise InvalidArgumentError(
            f'A request matcher\'s "{field_name}" is not a valid pattern: {error}.',
        ) from error
