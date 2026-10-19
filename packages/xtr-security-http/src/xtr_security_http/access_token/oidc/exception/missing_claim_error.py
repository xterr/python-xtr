"""A claim an OIDC answer was expected to carry is not on it."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["MissingClaimError"]


class MissingClaimError(AuthenticationError):
    """A claim an OIDC answer was expected to carry is not on it.

    Raised when the claim naming the user is missing or empty on an OIDC
    server's answer — a token whose granted scopes leave the claim out, say.
    The handler that reads the answer wraps it into an
    :class:`~xtr_security_http.exception.InvalidAccessTokenError`, so the
    chain names the missing claim while the caller learns only that the
    credentials were rejected.
    """

    MESSAGE_KEY: ClassVar[str] = "Missing claim."
