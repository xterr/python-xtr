"""A project name that cannot name both a distribution and an import package."""

from __future__ import annotations

from typing import final

from .cli_error import CliError

__all__ = ["InvalidProjectNameError"]


@final
class InvalidProjectNameError(CliError):
    """The name asked for, or the directory it was read from, cannot name the project.

    The name becomes the distribution, the console script and — dashes turned
    into underscores — the import package under ``src/``. A name that is not a
    valid identifier once turned, is a keyword, or would shadow a module of the
    standard library would leave an application that cannot import itself.

    Attributes:
        name: The name as it was given.
        reason: Why it cannot be used.
    """

    name: str
    reason: str

    def __init__(self, name: str, reason: str) -> None:
        """Record the name and why it was refused."""
        self.name = name
        self.reason = reason
        super().__init__(f"{name!r} cannot name a project: {reason}; pass --name to choose another")
