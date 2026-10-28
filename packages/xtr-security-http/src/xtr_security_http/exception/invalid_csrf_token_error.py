"""The forgery token a passport carried did not check out."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["InvalidCsrfTokenError"]


class InvalidCsrfTokenError(AuthenticationError):
    """A cross-site request forgery token was presented but could not be vouched for.

    The passport carried a token badge, and the value the request presented
    with it did not match what the token manager stored under the badge's id —
    or the request presented no value at all. The login the badge was meant to
    guard is refused: a request the page that rendered the form did not ask
    for cannot authenticate through it.
    """

    MESSAGE_KEY: ClassVar[str] = "Invalid CSRF token."
