"""Email handed to a local sendmail, over SMTP on its standard streams or piped to its input."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_mailer.exception import InvalidArgumentError

from ._sendmail_command import (
    delivery_arguments,
    is_interactive,
    piped_message,
    sendmail_arguments,
)
from ._sendmail_process import pipe_to_sendmail
from .abstract_transport import AbstractTransport
from .smtp._sendmail_smtp_transport import SendmailSmtpTransport
from .stoppable_transport_interface import StoppableTransportInterface

if TYPE_CHECKING:
    from typing import Self

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_mime import RawMessage

    from xtr_mailer.envelope import Envelope
    from xtr_mailer.sent_message import SentMessage

__all__ = ["SendmailTransport"]

_DEFAULT_TIMEOUT = 60.0


@final
class SendmailTransport(AbstractTransport, StoppableTransportInterface):
    """Sends email through the sendmail program of the host — sendmail, Postfix, Exim, msmtp.

    The command picks the mode, by holding ``-bs`` or ``-t`` among other flags:

    - ``-bs`` (the default, ``/usr/sbin/sendmail -bs``) speaks SMTP with the program over its
      standard streams, exactly as with a server: a refusal is reported as the server's would
      be, and the session stays open from one email to the next until :meth:`stop`. The program
      is run for each session and waited for after it.
    - ``-t`` runs the program once per email and writes the email to its input. The envelope's
      recipients are handed as arguments, after ``--``, and ``-t`` itself is left out, so a Bcc
      is never delivered from the headers; the envelope's sender is handed with ``-f`` unless
      the command gives one. Line endings become LF, and without ``-i`` or ``-oi`` a dot
      starting a line is doubled. A status other than ``0`` fails the send, with the start of
      what the program wrote, escaped.

    The command is split into arguments as a POSIX shell splits words, but never run through a
    shell: nothing in it is expanded. A program still running after the timeout — 60 seconds,
    see :meth:`set_timeout` — or when a send is cancelled is killed and waited for; none is
    left behind. :meth:`stop` never raises.
    """

    #: The command run when none is given: the conventional sendmail, in SMTP mode.
    DEFAULT_COMMAND: Final = "/usr/sbin/sendmail -bs"

    def __init__(
        self,
        command: str = DEFAULT_COMMAND,
        *,
        event_dispatcher: EventDispatcherInterface | None = None,
        logger: LoggerInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Prepare to run ``command``; nothing runs until an email is sent.

        Raises:
            InvalidArgumentError: ``command`` holds a control character, does not parse, or
                holds neither ``-bs`` nor ``-t``.
        """
        super().__init__(event_dispatcher, logger, clock)
        self._command: str = command
        self._arguments: list[str] = sendmail_arguments(command)
        self._timeout: float = _DEFAULT_TIMEOUT
        self._session: SendmailSmtpTransport | None = None
        if is_interactive(self._arguments):
            self._session = SendmailSmtpTransport(
                command, event_dispatcher=event_dispatcher, logger=logger, clock=clock
            )

    def set_timeout(self, seconds: float) -> Self:
        """Wait at most ``seconds`` for the program: for each reply, or to read an email and exit.

        Raises:
            InvalidArgumentError: ``seconds`` is not a positive, finite number.
        """
        if not (math.isfinite(seconds) and seconds > 0):
            raise InvalidArgumentError(
                f'The sendmail timeout must be a positive number of seconds, "{seconds}" given.'
            )
        self._timeout = float(seconds)
        if self._session is not None:
            _ = self._session.set_timeout(seconds)
        return self

    def get_timeout(self) -> float:
        """Return how long the program is waited for, in seconds."""
        return self._timeout

    @override
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        """Send ``message`` over the SMTP session in ``-bs`` mode, else pipe it to the program."""
        if self._session is not None:
            return await self._session.send(message, envelope)
        return await super().send(message, envelope)

    @override
    async def stop(self) -> None:
        """End the SMTP session and wait for the program; nothing to end in ``-t`` mode."""
        if self._session is not None:
            await self._session.stop()

    @override
    def __str__(self) -> str:
        """Name it ``smtp://sendmail``."""
        return "smtp://sendmail"

    @override
    async def _do_send(self, message: SentMessage) -> None:
        self._logger.debug('Email transport "{transport}" starting', {"transport": str(self)})
        arguments = delivery_arguments(self._arguments, message.get_envelope())
        data = piped_message(b"".join(message.to_iterable()), self._arguments)
        await pipe_to_sendmail(arguments, data, self._timeout)
        self._logger.debug('Email transport "{transport}" stopped', {"transport": str(self)})
