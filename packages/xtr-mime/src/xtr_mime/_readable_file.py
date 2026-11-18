"""Refuses a path a guesser cannot read before anything looks at what is there."""

from __future__ import annotations

import os
from pathlib import Path

from .exception import InvalidArgumentError

__all__ = ["ensure_readable_file"]


def ensure_readable_file(path: str) -> None:
    """Refuse ``path`` unless it names a regular file this process may read.

    A missing path, a directory and a file without read permission get the same answer: the
    caller handed in a path no guesser can work with, whichever way it guesses.

    Raises:
        InvalidArgumentError: When ``path`` is not a readable file.
    """
    if not (Path(path).is_file() and os.access(path, os.R_OK)):
        raise InvalidArgumentError(f'The "{path}" file does not exist or is not readable.')
