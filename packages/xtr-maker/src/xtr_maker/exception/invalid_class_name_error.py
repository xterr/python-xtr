"""A name typed for a class that cannot become one."""

from __future__ import annotations

from .maker_error import MakerError

__all__ = ["InvalidClassNameError"]


class InvalidClassNameError(MakerError, ValueError):
    """A name typed for a class that cannot become one.

    Raised before anything is rendered, so a person is asked again rather than
    handed a file that does not import. Also a :class:`ValueError`, which is
    what a question's validator raises to have the question asked again.

    Attributes:
        name: The name as it was typed.
        reason: Why it cannot be used.
    """

    name: str
    reason: str

    def __init__(self, name: str, reason: str) -> None:
        """Record the name and why it was refused."""
        self.name = name
        self.reason = reason
        super().__init__(f"{name!r} cannot name a class: {reason}")
