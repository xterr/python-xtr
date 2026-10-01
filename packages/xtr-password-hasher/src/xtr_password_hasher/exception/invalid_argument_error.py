"""A hasher or a config was given an argument it cannot work with."""

from __future__ import annotations

from .password_hasher_error import PasswordHasherError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(PasswordHasherError, ValueError):
    """A hasher or a config was configured with a value it cannot use.

    Raised where the value is given — a bcrypt cost outside 4 to 31, a PBKDF2
    iteration count below a safe floor, a hash algorithm the platform does not
    provide, an algorithm no hasher implements, rather than on the first hash.

    Also a :class:`ValueError`, so code that already guards its configuration
    with ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        reason: What is wrong with the argument.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        """Record what is wrong with the argument."""
        self.reason = reason
        super().__init__(reason)
