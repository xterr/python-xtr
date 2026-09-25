"""Something was popped off a stack that holds nothing."""

from __future__ import annotations

from xtr_logging_contracts import LoggingError

__all__ = ["EmptyStackError"]


class EmptyStackError(LoggingError):
    """Something was popped off a stack that holds nothing.

    Raised by ``pop_handler`` and ``pop_processor``. Popping more than was
    pushed is always a bug in the code doing it, so it is refused rather than
    answered with ``None``.
    """

    owner: str
    stack: str

    def __init__(self, owner: str, stack: str) -> None:
        """Record what was popped from, and which of its stacks was empty."""
        self.owner = owner
        self.stack = stack
        super().__init__(f"cannot pop from the empty {stack} stack of {owner}")
