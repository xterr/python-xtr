"""A Python version the new project cannot be pinned to."""

from __future__ import annotations

from typing import final

from .cli_error import CliError

__all__ = ["UnsupportedPythonError"]


@final
class UnsupportedPythonError(CliError):
    """``--python`` is not a ``3.<minor>`` version the packages support.

    Every xtr package requires Python 3.11 or later, so a project pinned below
    that could install none of them.

    Attributes:
        python: The version as it was given.
    """

    python: str

    def __init__(self, python: str) -> None:
        """Record the version that was refused."""
        self.python = python
        super().__init__(f"--python {python!r}: give a version 3.11 or later, such as 3.13")
