"""The authentication error raised when a presented token cannot be trusted."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["InvalidTokenError"]


class InvalidTokenError(AuthenticationError):
    """A caller presented a token that is malformed, unsigned or tampered with.

    The catch-all for a token the verifier refused for any reason other than
    expiry: a bad signature, a disallowed algorithm, a structural fault. Drawn
    from :class:`~xtr_security_core.exception.AuthenticationError`.
    """

    MESSAGE_KEY: ClassVar[str] = "Invalid JWT Token"
