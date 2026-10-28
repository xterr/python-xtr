"""An SMTP server's reply other than the one a command expects."""

from __future__ import annotations

from .transport_error import TransportError

__all__ = ["UnexpectedResponseError"]


class UnexpectedResponseError(TransportError):
    """An SMTP server replied to a command with a code the command does not accept.

    Its :attr:`code` is the reply code the server sent: an SMTP transport resets
    the session after a refusal, but not after ``421``, the server closing the
    connection, and authentication tries the next mechanism after one.
    """
