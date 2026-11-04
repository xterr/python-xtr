"""Builds sendmail transports from ``sendmail://`` and ``sendmail+smtp://`` DSNs."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_mailer.exception import InvalidArgumentError, UnsupportedSchemeError

from .abstract_transport_factory import AbstractTransportFactory
from .sendmail_transport import SendmailTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .dsn import Dsn

__all__ = ["SendmailTransportFactory"]


@final
class SendmailTransportFactory(AbstractTransportFactory):
    """Builds a :class:`SendmailTransport` for ``sendmail://`` and ``sendmail+smtp://``.

    The host is not read — ``sendmail://default`` is the usual DSN. The ``command`` option
    names the program and its flags, URL-encoded, ``-bs`` or ``-t`` among them:
    ``sendmail://default?command=/usr/sbin/sendmail%20-oi%20-t``; without it the transport
    runs ``/usr/sbin/sendmail -bs``.
    """

    @override
    def create(self, dsn: Dsn) -> SendmailTransport:
        """Build the sendmail transport ``dsn`` describes; nothing runs yet.

        Raises:
            UnsupportedSchemeError: ``dsn``'s scheme is neither ``sendmail`` nor
                ``sendmail+smtp``.
            InvalidArgumentError: The ``command`` option is not one command holding ``-bs`` or
                ``-t``.
        """
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "sendmail", self._get_supported_schemes())
        match dsn.get_option("command", SendmailTransport.DEFAULT_COMMAND):
            case str() as command:
                return SendmailTransport(
                    command, event_dispatcher=self._event_dispatcher, logger=self._logger
                )
            case _:
                raise InvalidArgumentError(
                    'The "command" option is not valid: it must be a sendmail command.'
                )

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        """Return ``sendmail`` and ``sendmail+smtp``."""
        return ("sendmail", "sendmail+smtp")
