"""The authentication error raised when no token reached a protected resource."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["MissingTokenError"]


class MissingTokenError(AuthenticationError):
    """A request reached a protected resource carrying no token at all.

    Raised by the authenticator's entry point when a firewall needs
    authentication and no extractor found a token, so the challenge names that
    the token was missing rather than wrong.
    """

    MESSAGE_KEY: ClassVar[str] = "JWT Token not found"
