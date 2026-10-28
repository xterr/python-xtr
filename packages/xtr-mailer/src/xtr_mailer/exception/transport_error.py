"""A transport that could not hand an email over."""

from __future__ import annotations

from .mailer_runtime_error import MailerRuntimeError

__all__ = ["TransportError"]


class TransportError(MailerRuntimeError):
    """A server could not be reached, or refused an email.

    It is the one error a round-robin or failover transport takes as a sign that
    a transport is down: anything else is a mistake that another transport would
    make too.

    Attributes:
        code: The reply code the server refused with — an SMTP reply code, an HTTP
            status — or ``0`` when there was none. SMTP transports tell a refusal
            from a dropped connection by it.
        debug: The protocol transcript up to the failure, so a caller can see what
            was said. Authentication exchanges are kept out of it: it never
            carries credentials.
    """

    code: int
    debug: str

    def __init__(self, message: str, code: int = 0) -> None:
        """Record why the email could not be handed over.

        Args:
            message: Why the transport failed.
            code: The reply code the server refused with, ``0`` when there was none.
        """
        self.code = code
        self.debug = ""
        super().__init__(message)

    def append_debug(self, debug: str) -> None:
        """Add ``debug`` to the transcript.

        The error is raised from deep inside a transport, which only knows its
        own part of the exchange; each layer it passes through appends what it saw.
        """
        self.debug += debug
