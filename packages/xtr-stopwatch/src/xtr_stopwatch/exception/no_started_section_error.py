"""A section was stopped while none was open."""

from __future__ import annotations

from .stopwatch_error import StopwatchError

__all__ = ["NoStartedSectionError"]


class NoStartedSectionError(StopwatchError):
    """A section was stopped while none was open.

    The root section is always open and is never stopped, so stopping with
    only the root in place has nothing to stop.

    Attributes:
        section_id: The id the section would have been stored under.
    """

    section_id: str

    def __init__(self, section_id: str) -> None:
        """Record the id the stop was asked for."""
        self.section_id = section_id
        super().__init__(f'there is no started section to stop as "{section_id}"')
