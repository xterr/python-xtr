"""No credentials were presented where some were required."""

from __future__ import annotations

from typing import ClassVar

from .authentication_error import AuthenticationError

__all__ = ["AuthenticationCredentialsNotFoundError"]


class AuthenticationCredentialsNotFoundError(AuthenticationError):
    """No authentication credentials were found in the request.

    Distinct from rejected credentials: nothing was presented at all, so the
    caller is anonymous where authentication was required.
    """

    MESSAGE_KEY: ClassVar[str] = "Full authentication is required to access this resource."
