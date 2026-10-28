"""A DSN missing a part its transport needs."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError

__all__ = ["IncompleteDsnError"]


class IncompleteDsnError(InvalidArgumentError):
    """A DSN parses, but lacks a part its transport cannot work without — a user, a password.

    The message names the missing part only, never the DSN, which carries credentials.
    """
