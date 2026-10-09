"""A project with several web entry points, and no way to ask which one to serve."""

from __future__ import annotations

from typing import final

from .cli_error import CliError

__all__ = ["AmbiguousWebEntryPointError"]


@final
class AmbiguousWebEntryPointError(CliError):
    """Several web entry points were found and questions are off.

    Attributes:
        candidates: The entry points found, as ``--entrypoint`` takes them.
    """

    candidates: tuple[str, ...]

    def __init__(self, candidates: tuple[str, ...]) -> None:
        """Record what could have been served."""
        self.candidates = candidates
        super().__init__(
            f"several web entry points ({', '.join(candidates)}): pass --entrypoint to choose one"
        )
