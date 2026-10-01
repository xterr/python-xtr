"""The authentication error raised when a presented token has expired."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["ExpiredTokenError"]


class ExpiredTokenError(AuthenticationError):
    """A caller presented a token whose expiry has passed.

    Drawn from the family's :class:`~xtr_security_core.exception.AuthenticationError`
    so the firewall turns it into a challenge; its public message names the
    expiry rather than leaking why the token was refused.
    """

    MESSAGE_KEY: ClassVar[str] = "Expired JWT Token"
