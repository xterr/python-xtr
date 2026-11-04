"""A way of logging in to an SMTP server."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_mailer.transport.smtp.esmtp_transport import EsmtpTransport

__all__ = ["AuthenticatorInterface"]


@runtime_checkable
class AuthenticatorInterface(Protocol):
    """Logs in with one ``AUTH`` mechanism, through the transport's own session.

    An :class:`~xtr_mailer.transport.smtp.EsmtpTransport` tries each of its authenticators
    whose mechanism the server offers, in order, until one is accepted. One the server
    refuses raises an :class:`~xtr_mailer.exception.UnexpectedResponseError`, and the next
    is tried; any other error ends the attempt.
    """

    def get_auth_keyword(self) -> str:
        """Return the mechanism's name as ``EHLO`` advertises it: ``PLAIN``, ``CRAM-MD5``."""
        ...

    async def authenticate(self, client: EsmtpTransport) -> None:
        """Log in as the transport's user, with its password.

        Each line goes through :meth:`EsmtpTransport.execute_command`.

        Raises:
            UnexpectedResponseError: The server refused the credentials or the exchange.
            TransportError: The session was lost.
        """
        ...
