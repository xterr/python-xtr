"""A plaintext password was longer than any hasher will process."""

from __future__ import annotations

from .password_hasher_error import PasswordHasherError

__all__ = ["InvalidPasswordError"]


class InvalidPasswordError(PasswordHasherError, ValueError):
    """A plaintext password exceeded the length a hasher accepts.

    Raised by :meth:`hash` when the input is longer than
    ``MAX_PASSWORD_LENGTH``. Refusing an unbounded input keeps a hasher from
    spending unbounded work on it — a denial-of-service guard, not a policy on
    how long a password may be. Verifying an over-long input never raises: it
    simply cannot match a hash made from a bounded one, so :meth:`verify`
    returns ``False``.

    Also a :class:`ValueError`, so code that already guards its input with
    ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        length: The UTF-8 byte length of the input that was refused.
        max_length: The greatest UTF-8 byte length a hasher accepts.
    """

    length: int
    max_length: int

    def __init__(self, length: int, max_length: int) -> None:
        """Record the refused UTF-8 byte length and the limit it crossed."""
        self.length = length
        self.max_length = max_length
        super().__init__(
            f"The password is {length} bytes long, more than the {max_length} a hasher accepts.",
        )
