"""A remember-me cookie was presented a second time."""

from __future__ import annotations

from typing import ClassVar

from .authentication_error import AuthenticationError

__all__ = ["CookieTheftError"]


class CookieTheftError(AuthenticationError):
    """A remember-me cookie carried a value that was already spent.

    A remember-me value is one-time: presenting it rotates it. The same
    value arriving twice means the cookie was copied — stolen — and the
    series it belongs to is dropped so the thief and the owner are both
    logged out.
    """

    MESSAGE_KEY: ClassVar[str] = "Cookie has already been used by someone else."
