"""The caller could not be identified."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar, Self, cast

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

    A failed login that redirects keeps its error in the session for the page
    that renders the form again, and a session keeps the public half only:
    :meth:`to_session` answers the key and the data, and :meth:`from_session`
    rebuilds an error of the same class whose internal message is the key —
    the internal message never reaches the session store.

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

    def to_session(self) -> dict[str, object]:
        """Return the public half of this error, for a session to keep.

        The key, and the entries of the data that come back from JSON exactly
        as they went in; an entry that would not is left out rather than
        refusing the error, since the data only decorates the key. The
        internal message is not part of it: it may name a user or a reason,
        and belongs in a log, never in a store outside the process.
        """
        data = self.message_data.items()
        return {
            "message_key": self.message_key,
            "message_data": {name: value for name, value in data if _round_trips({name: value})},
        }

    @classmethod
    def from_session(cls, message_key: str, message_data: Mapping[str, object]) -> Self:
        """Rebuild an error a session kept, as this class, from its public half.

        The class's constructor is not run — a subclass's asks for what the
        session never kept, a user or a status — so a subclass carrying more
        than the key and the data overrides this to settle the rest. The
        rebuilt error's internal message is the key: ``str(error)`` reads it.
        """
        error = cls.__new__(cls)
        AuthenticationError.__init__(
            error,
            None,
            message_key=message_key,
            message_data=message_data,
        )
        return error


def _round_trips(value: object) -> bool:
    """Tell whether ``value`` comes back from JSON exactly as it went in.

    A tuple comes back a list and a number keying an object a string, so
    neither does; a value JSON cannot write at all does not either.
    """
    try:
        encoded = json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return cast("object", json.loads(encoded)) == value
