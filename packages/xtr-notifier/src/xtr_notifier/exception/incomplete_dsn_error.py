"""A DSN missing a part its transport needs."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError

__all__ = ["IncompleteDsnError"]


class IncompleteDsnError(InvalidArgumentError):
    """A DSN parses, but lacks a part its transport cannot work without — a token, a user.

    Attributes:
        original_dsn: The DSN the part is missing from, as the caller chose to show
            it, or ``None``. Pass a form without credentials: the message names it.
    """

    original_dsn: str | None

    def __init__(self, message: str, dsn: str | None = None) -> None:
        """Say what is missing, and from which DSN.

        Args:
            message: What is missing.
            dsn: The DSN it is missing from, prefixed to the message when given.
                Never the raw DSN when it carries credentials.
        """
        self.original_dsn = dsn
        if dsn:
            message = f'Invalid "{dsn}" notifier DSN: {message}'
        super().__init__(message)
