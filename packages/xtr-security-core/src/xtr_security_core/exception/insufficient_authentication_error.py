"""The caller is authenticated, but not strongly enough for this resource."""

from __future__ import annotations

from typing import ClassVar

from .authentication_error import AuthenticationError

__all__ = ["InsufficientAuthenticationError"]


class InsufficientAuthenticationError(AuthenticationError):
    """Authentication succeeded, but not to the level this resource needs.

    Raised when access is denied to a caller who is not fully authenticated:
    the answer is to authenticate more strongly, not to be forbidden outright.
    """

    MESSAGE_KEY: ClassVar[str] = "Full authentication is required to access this resource."
