"""The authentication error raised when a token payload lacks the id claim."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError

__all__ = ["InvalidPayloadError"]


class InvalidPayloadError(AuthenticationError):
    """A verified token carried no claim naming the user it stands for.

    The signature checked, but the claim the manager reads the user's
    identifier from — the configured user-id claim — was absent, so the token
    proves nobody. Drawn from
    :class:`~xtr_security_core.exception.AuthenticationError`.

    Attributes:
        invalid_key: The claim the payload was expected to carry.
    """

    def __init__(self, invalid_key: str, message: str | None = None) -> None:
        """Record the ``invalid_key`` the payload did not carry."""
        self.invalid_key: str = invalid_key
        super().__init__(
            message
            if message is not None
            else f'Unable to find key "{invalid_key}" in the token payload.',
            message_key=f'Unable to find key "{invalid_key}" in the token payload.',
        )
