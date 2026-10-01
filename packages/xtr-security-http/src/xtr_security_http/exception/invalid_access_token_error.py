"""A bearer access token was malformed, expired or wrongly signed."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["InvalidAccessTokenError"]


class InvalidAccessTokenError(AuthenticationError):
    """A bearer access token could not be trusted.

    The token was present but malformed, expired, signed with the wrong key,
    or otherwise not verifiable. A protected resource answers such a token
    with a challenge naming ``invalid_token``.
    """

    MESSAGE_KEY: ClassVar[str] = "Invalid credentials."
