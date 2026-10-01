"""The machinery of authentication failed, not the credentials."""

from __future__ import annotations

from typing import ClassVar

from .authentication_error import AuthenticationError

__all__ = ["AuthenticationServiceError"]


class AuthenticationServiceError(AuthenticationError):
    """A service authentication relies on failed.

    A database that answers a user lookup, a remote key set that verifies a
    token — when one of these is unreachable, the caller is neither accepted
    nor rejected: the attempt could not be completed at all.
    """

    MESSAGE_KEY: ClassVar[str] = (
        "Authentication request could not be processed due to a system problem."
    )
