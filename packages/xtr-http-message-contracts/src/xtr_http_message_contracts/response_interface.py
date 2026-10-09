"""A response on its way out, as a server sends it."""

from __future__ import annotations

from typing import Protocol, Self, runtime_checkable

from .message_interface import MessageInterface

__all__ = ["ResponseInterface"]


@runtime_checkable
class ResponseInterface(MessageInterface, Protocol):
    """An outgoing, server-side response.

    On top of what every message carries — a protocol version, headers and a
    body — a response carries a status code and the reason phrase that goes
    with it.

    Responses are immutable. Every ``with_*`` method keeps the instance it was
    called on as it was and returns one carrying the change.
    """

    def get_status_code(self) -> int:
        """Return the status code of the response.

        Returns:
            The three-digit code saying how the server got on with the
            request.
        """
        ...

    def with_status(self, code: int, reason_phrase: str = "") -> Self:
        """Return an instance carrying ``code`` and, optionally, ``reason_phrase``.

        Given no reason phrase, an implementation may fill in the one
        recommended for that code — by the HTTP specification, or by the
        registry of status codes kept alongside it.

        Args:
            code: The three-digit status code to set.
            reason_phrase: The phrase to go with ``code``. Left out, the
                implementation may choose the recommended one.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the status code is not a valid one.
        """
        ...

    def get_reason_phrase(self) -> str:
        """Return the reason phrase that goes with the status code.

        A status line need not carry a reason phrase at all, so there may be
        none to report; an implementation may answer with the phrase
        recommended for the code instead — by the HTTP specification, or by
        the registry of status codes kept alongside it.

        Returns:
            The reason phrase, or an empty string when there is none.
        """
        ...
