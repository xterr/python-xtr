"""Email handed to a mail server over SMTP."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Final

from typing_extensions import override

from xtr_mailer.exception import (
    InvalidArgumentError,
    MailerError,
    TransportError,
    UnexpectedResponseError,
)
from xtr_mailer.transport.abstract_transport import AbstractTransport
from xtr_mailer.transport.stoppable_transport_interface import StoppableTransportInterface

from ._smtp_client import SmtpClient
from ._smtp_connection_config import SmtpConnectionConfig
from ._smtp_connection_settings import SmtpConnectionSettings

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_mime import RawMessage

    from xtr_mailer.envelope import Envelope
    from xtr_mailer.sent_message import SentMessage

__all__ = ["SmtpTransport"]

_MESSAGE_ID: Final = re.compile(
    r"^250 (?:\S+ )?Ok:?+ (?:queued as |id=)?+(?P<id>[A-Z0-9._-]++)", re.IGNORECASE | re.MULTILINE
)
_SERVICE_CLOSING: Final = 421


class SmtpTransport(AbstractTransport, SmtpConnectionSettings, StoppableTransportInterface):
    """Sends each email over one SMTP session, kept open from one email to the next.

    The session opens with the first email: the greeting, then ``HELO`` naming the local
    domain. Each email is an envelope — ``MAIL FROM``, a ``RCPT TO`` per recipient — and its
    bytes after ``DATA``; the server's acceptance may name the id it queued it as, which
    becomes the sent message's id. The exchange, credentials taken out, is the sent
    message's debug log.

    A refusal leaves the session usable: it is reset with ``RSET`` for the next email. A
    ``421`` — the server closing the channel — a lost connection or a timeout end it, and the
    next email opens a new one. An email idle longer than the ping threshold is preceded by a
    ``NOOP``, a new session opened when it fails; after the restart threshold's count of
    emails the session is ended, and the next email opens a new one after the restart sleep.

    One session carries one email at a time: emails sent at once through one transport take
    turns on it. The pace :meth:`set_max_per_second` sets spaces their starts — before
    listeners run and the email is rendered — so the session may carry them further apart,
    never closer. A cancelled send closes the session at once, its state unknown, and is no
    failure. :meth:`stop` ends the session and never raises.
    """

    def __init__(  # noqa: PLR0913 — the server's address and the collaborators every transport takes
        self,
        host: str = "localhost",
        port: int = 465,
        tls: bool = True,
        *,
        event_dispatcher: EventDispatcherInterface | None = None,
        logger: LoggerInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Prepare a session with ``host`` on ``port``; nothing connects until an email is sent.

        Args:
            host: The server's name or address.
            port: The server's port.
            tls: Speak TLS from the first byte (``smtps``).
            event_dispatcher: Where the email events go; ``None`` announces nothing.
            logger: Where the session's start and end are logged.
            clock: What the ping threshold, the restart sleep and the pace are measured on.
        """
        super().__init__(event_dispatcher, logger, clock)
        self._config: SmtpConnectionConfig = SmtpConnectionConfig(host, port, tls)
        self._client: SmtpClient = SmtpClient(self._config)
        self._lock: asyncio.Lock = asyncio.Lock()
        self._started: bool = False
        self._restart_threshold: int = 100
        self._restart_threshold_sleep: float = 0.0
        self._restart_counter: int = 0
        self._ping_threshold: float = 100.0
        self._last_message_time: float = 0.0

    def set_restart_threshold(self, threshold: int, sleep: float = 0) -> Self:
        """End the session after ``threshold`` emails, ``0`` never; wait ``sleep`` seconds then."""
        self._restart_threshold = threshold
        self._restart_threshold_sleep = sleep
        return self

    def set_ping_threshold(self, seconds: float) -> Self:
        """``NOOP`` before an email idle over ``seconds`` (100); servers drop chatty sessions."""
        self._ping_threshold = seconds
        return self

    @override
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        """Send ``message`` on the session, then end it if the restart threshold is reached."""
        sent = await super().send(message, envelope)
        async with self._lock:
            await self._check_restart_threshold()
        return sent

    async def start(self) -> None:
        """Open the session now, rather than with the first email; nothing if it is open."""
        async with self._lock:
            await self._start()

    @override
    async def stop(self) -> None:
        """End the session with ``QUIT``; the next email opens a new one.

        Never raises: a server refusing ``QUIT`` or gone already is logged, and the
        connection closed all the same.
        """
        async with self._lock:
            await self._stop()

    async def execute_command(self, command: str, codes: Sequence[int]) -> str:
        """Send ``command`` on the session and return the reply, which must have one of ``codes``.

        Every command of the session but an ``EHLO`` and ``STARTTLS`` goes through here, so a
        subclass can change one. An authenticator logs in with it, while the session's turn
        is held; called from anywhere else, it would cut into an email being sent.

        Raises:
            LogicError: ``codes`` is empty.
            UnexpectedResponseError: The reply has another code.
            TransportError: The session was lost, or the reply did not come in time.
        """
        return await self._client.execute(command, codes)

    @override
    def __str__(self) -> str:
        """Name it ``smtp://host``, ``smtps://`` over TLS, with the port unless the default."""
        return self._server_name()

    @override
    async def _do_send(self, message: SentMessage) -> None:
        async with self._lock:
            await self._send_on_session(message)

    def _parse_message_id(self, mta_result: str) -> str:
        """Return the id the server's acceptance names, ``""`` when it names none."""
        found = _MESSAGE_ID.search(mta_result)
        return found["id"] if found else ""

    def _server_supports_smtp_utf8(self) -> bool:
        """Whether the server takes addresses with a non-ASCII local part; plain SMTP does not."""
        return False

    async def _send_on_session(self, message: SentMessage) -> None:
        try:
            if self._clock.now().timestamp() - self._last_message_time > self._ping_threshold:
                await self._ping()
            await self._start()
            envelope = message.get_envelope()
            await self._do_mail_from_command(
                envelope.get_sender().get_encoded_address(),
                envelope.any_address_has_unicode_localpart(),
            )
            for recipient in envelope.get_recipients():
                await self._do_rcpt_to_command(recipient.get_encoded_address())
            _ = await self.execute_command("DATA", [354])
            mta_result = await self._client.message(b"".join(message.to_iterable()))
        except TransportError as error:
            self._last_message_time = 0.0
            await self._recover(error)
            raise
        except MailerError:
            raise  # Refused before a word was sent: the session is as it was.
        except BaseException:
            self._terminate()  # Cancelled mid-exchange: what the server heard is unknown.
            raise
        message.append_debug(self._client.take_transcript())
        self._last_message_time = self._clock.now().timestamp()
        if message_id := self._parse_message_id(mta_result):
            message.set_message_id(message_id)

    async def _do_mail_from_command(self, address: str, smtputf8: bool) -> None:
        if smtputf8 and not self._server_supports_smtp_utf8():
            raise InvalidArgumentError(
                "The SMTP server does not support the SMTPUTF8 extension required to send to "
                "addresses with non-ASCII characters in their local-part."
            )
        option = " SMTPUTF8" if smtputf8 else ""
        _ = await self.execute_command(f"MAIL FROM:<{address}>{option}", [250])

    async def _do_rcpt_to_command(self, address: str) -> None:
        _ = await self.execute_command(f"RCPT TO:<{address}>", [250, 251, 252])

    async def _recover(self, error: TransportError) -> None:
        """Reset the session after a refusal; end it after anything else."""
        if not self._started:
            return
        try:
            if isinstance(error, UnexpectedResponseError) and error.code != _SERVICE_CLOSING:
                # The server answered: the session is in step and can be reused once reset.
                _ = await self.execute_command("RSET", [250])
            else:
                # A 421 closes the channel; a timeout or a lost connection may leave a reply
                # unread, which the next command would take for its own.
                await self._stop()
        except TransportError:
            if not self._client.is_connected:
                await self._stop()
        except BaseException:
            self._terminate()  # Cancelled mid-reset: its reply may still be on its way.
            raise
        _ = self._client.take_transcript()

    async def _start(self) -> None:
        if self._started:
            return
        self._log('Email transport "{transport}" starting')
        client = self._client = SmtpClient(self._config)
        try:
            _ = await client.connect()
            _ = await self.execute_command(f"HELO {self.get_local_domain()}", [250])
        except BaseException:
            client.close()
            raise
        self._started = True
        self._last_message_time = 0.0
        self._log('Email transport "{transport}" started')

    async def _stop(self) -> None:
        if not self._started:
            return
        self._log('Email transport "{transport}" stopping')
        try:
            _ = await self.execute_command("QUIT", [221])
        except TransportError as error:
            self._logger.debug(
                'Email transport "{transport}" could not quit cleanly: {reason}',
                {"transport": str(self), "reason": str(error)},
            )
        finally:
            self._terminate()

    def _terminate(self) -> None:
        if self._started:
            self._client.close()
            self._started = False
            self._log('Email transport "{transport}" stopped')

    async def _ping(self) -> None:
        if not self._started:
            return
        try:
            _ = await self.execute_command("NOOP", [250])
            alive = self._client.is_connected and not self._client.has_pending_data
        except TransportError:
            alive = False
        if not alive:
            # Also when a reply waits behind the NOOP's (a 421): the next command would read it.
            await self._stop()

    async def _check_restart_threshold(self) -> None:
        if not self._started or self._restart_threshold <= 0:
            return
        self._restart_counter += 1
        if self._restart_counter < self._restart_threshold:
            return
        await self._stop()
        self._restart_counter = 0
        if (sleep := self._restart_threshold_sleep) > 0:
            self._logger.debug(
                'Email transport "{transport}" sleeps for {seconds} seconds after stopping',
                {"transport": str(self), "seconds": sleep},
            )
            await self._clock.sleep_async(sleep)

    def _log(self, message: str) -> None:
        self._logger.debug(message, {"transport": str(self)})
