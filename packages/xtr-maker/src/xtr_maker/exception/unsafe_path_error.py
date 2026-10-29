"""A path a maker was asked to write that lies outside the project, or is a symbolic link."""

from __future__ import annotations

from .maker_error import MakerError

__all__ = ["UnsafePathError"]


class UnsafePathError(MakerError, OSError):
    """A path a maker was asked to write that lies outside the project, or is a symbolic link.

    A name typed at a prompt ends up in a path, so every path is checked
    before a byte is written: one climbing out of the project, or a link
    pointing anywhere, is refused rather than followed.

    Also an :class:`OSError`, so code catching filesystem failures keeps
    working.

    Attributes:
        path: The path as it was given.
        reason: Why it was refused.
    """

    path: str
    reason: str

    def __init__(self, path: str, reason: str) -> None:
        """Record the path and why it was refused."""
        self.path = path
        self.reason = reason
        super().__init__(f"cannot write {path}: {reason}")
