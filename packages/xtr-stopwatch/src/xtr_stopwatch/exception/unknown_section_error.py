"""A section was reopened that the current one does not hold."""

from __future__ import annotations

from .stopwatch_error import StopwatchError

__all__ = ["UnknownSectionError"]


class UnknownSectionError(StopwatchError, LookupError):
    """A section was reopened by an id the current section holds no child under.

    Reopening adds periods to a section that was stopped earlier, and that is
    only meaningful at the level it lives at: a section started elsewhere is
    refused rather than silently begun afresh here.

    Also a :class:`LookupError`, as a missing key is.

    Attributes:
        section_id: The id that is not a child of the current section.
    """

    section_id: str

    def __init__(self, section_id: str) -> None:
        """Record the id that was asked for."""
        self.section_id = section_id
        super().__init__(
            f'section "{section_id}" was started at another level and cannot be opened here'
        )
