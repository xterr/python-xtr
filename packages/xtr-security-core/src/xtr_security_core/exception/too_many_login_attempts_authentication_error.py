"""Too many failed login attempts; the caller must wait before retrying."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override

from .authentication_error import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["TooManyLoginAttemptsAuthenticationError"]


class TooManyLoginAttemptsAuthenticationError(AuthenticationError):
    """Login is refused because the caller failed too many times.

    A throttling listener raises this once the failed attempts cross its
    limit. The public key says how long the caller must wait, when the
    limiter could say: the wait is the only thing the caller can act on.

    Rebuilt from a session, it reads the wait back from its own data, where
    the key's ``%minutes%`` keeps it.

    Attributes:
        threshold: The minutes the caller must wait, or ``None`` when the
            wait is not quantified.
    """

    threshold: int | None

    def __init__(self, threshold: int | None = None) -> None:
        """Record the wait and compose the public key from it.

        Args:
            threshold: The minutes the caller must wait, if the limiter
                could count them.
        """
        self.threshold = threshold
        if threshold:
            minutes = "%minutes% minutes." if threshold > 1 else "%minutes% minute."
            key = f"Too many failed login attempts, please try again in {minutes}"
        else:
            key = "Too many failed login attempts, please try again later."
        super().__init__(
            key,
            message_key=key,
            message_data={"%minutes%": threshold, "%count%": 0 if threshold is None else threshold},
        )

    @classmethod
    @override
    def from_session(cls, message_key: str, message_data: Mapping[str, object]) -> Self:
        """Rebuild the error a session kept, the wait read back from ``%minutes%``."""
        error = super().from_session(message_key, message_data)
        minutes = message_data.get("%minutes%")
        error.threshold = None
        if isinstance(minutes, int) and not isinstance(minutes, bool):
            error.threshold = minutes
        return error
