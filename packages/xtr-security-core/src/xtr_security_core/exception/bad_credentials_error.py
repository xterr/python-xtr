"""The credentials presented were rejected."""

from __future__ import annotations

from typing import ClassVar

from .authentication_error import AuthenticationError

__all__ = ["BadCredentialsError"]


class BadCredentialsError(AuthenticationError):
    """The credentials presented were rejected.

    The public catch-all of authentication: a wrong password, a malformed
    token, or a masked sensitive failure all surface as this, so a client
    learns only that its credentials did not work.
    """

    MESSAGE_KEY: ClassVar[str] = "Invalid credentials."
