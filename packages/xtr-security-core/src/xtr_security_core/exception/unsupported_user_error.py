"""A user of a class no provider or checker was meant for was given."""

from __future__ import annotations

from .security_error import SecurityError

__all__ = ["UnsupportedUserError"]


class UnsupportedUserError(SecurityError, TypeError):
    """A user of the wrong class reached a provider, checker or resolver.

    Also a :class:`TypeError`: the object is not the kind of user the code was
    configured to work with, a mistake in wiring rather than in credentials.
    """
