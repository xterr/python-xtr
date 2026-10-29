"""A file a maker would write that already exists, or is already about to be written."""

from __future__ import annotations

from .maker_error import MakerError

__all__ = ["TargetExistsError"]


class TargetExistsError(MakerError, FileExistsError):
    """A file a maker would write that already exists, or is already about to be written.

    Makers never overwrite: code someone wrote, or edited after a maker wrote
    it, is theirs. The error is raised when the file is queued, before
    anything is written, so a maker writing several files writes none of them.

    Also a :class:`FileExistsError`, so code catching that keeps working.

    Attributes:
        path: The file, relative to the project directory.
    """

    path: str

    def __init__(self, path: str) -> None:
        """Record the file that is in the way."""
        self.path = path
        super().__init__(f"{path} already exists; remove it or pick another name")
