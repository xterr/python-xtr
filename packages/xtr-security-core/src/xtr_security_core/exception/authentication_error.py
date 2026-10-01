"""The caller could not be identified."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from .security_error import SecurityError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["AuthenticationError"]


class AuthenticationError(SecurityError):
    """Authentication failed: who is calling could not be established.

    An authentication error separates two messages. The one passed to
    :class:`Exception` is internal — it may name a user, a claim or a reason,
    and belongs in a log, never in a response. :attr:`message_key` is the safe
    public text a client may see, and :attr:`message_data` the values a
    presentation layer substitutes into it. Keeping them apart is what lets a
    failure be logged in full while the client learns only that credentials
    were rejected.

    Attributes:
        message_key: Safe, public text describing the failure.
        message_data: Values a presentation layer may substitute into the key.
    """

    #: The default public text for this class of error.
    MESSAGE_KEY: ClassVar[str] = "An authentication exception occurred."

    message_key: str
    message_data: dict[str, object]

    def __init__(
        self,
        message: str | None = None,
        *,
        message_key: str | None = None,
        message_data: Mapping[str, object] | None = None,
    ) -> None:
        """Record the internal message and the safe public key and data.

        Args:
            message: The internal message; defaults to the public key.
            message_key: The safe public text; defaults to :attr:`MESSAGE_KEY`.
            message_data: Values for the public key.
        """
        self.message_key = message_key if message_key is not None else self.MESSAGE_KEY
        self.message_data = dict(message_data) if message_data is not None else {}
        super().__init__(message if message is not None else self.message_key)

    def get_message_key(self) -> str:
        """Return the safe public text for this error."""
        return self.message_key

    def get_message_data(self) -> Mapping[str, object]:
        """Return the values a presentation layer substitutes into the key."""
        return self.message_data
