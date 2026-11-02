"""One SMTP session, driven command by command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import aiosmtplib

from xtr_mailer.exception import (
    InvalidArgumentError,
    LogicError,
    MailerError,
    TransportError,
    UnexpectedResponseError,
)
from xtr_mailer.transport.smtp._smtp_reply import render_reply, unexpected_response
from xtr_mailer.transport.smtp._smtp_transcript import SmtpTranscript

from ._errors import failure, response_of, unreachable
from ._session import open_session, parse_capabilities
from ._tls import peer_matches, upgrade
from ._upload import send_message

if TYPE_CHECKING:
    import socket
    from collections.abc import Awaitable, Callable, Sequence

    from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig

__all__ = ["SmtpClient"]

_AUTH_CONTINUE: Final = 334
_MESSAGE: Final = "[message]"


@final
class SmtpClient:
    """An SMTP session a transport drives one command at a time.

    Each command states the reply codes it accepts; any other reply raises an
    :class:`UnexpectedResponseError` carrying the code, which is how a transport
    tells a refusal it can recover from (reset, try the next authenticator) from
    a closed channel. A lost or silent connection raises a :class:`TransportError`.
    Either error's ``debug`` holds the failing command and its reply — never the
    lines of an ``AUTH`` exchange, which carry credentials, nor a secret the server
    echoes back (see :class:`SmtpTranscript`). The exchanges that went through are kept
    for :meth:`take_transcript`, redacted the same way.
    """

    __slots__ = (
        "_authenticating",
        "_capabilities",
        "_config",
        "_description",
        "_smtp",
        "_transcript",
    )

    def __init__(self, config: SmtpConnectionConfig) -> None:
        """Prepare a session; nothing connects until :meth:`connect`.

        Raises:
            InvalidArgumentError: The local hostname has whitespace or control characters.
        """
        self._config = config
        self._description = config.description
        self._capabilities: dict[str, list[str]] = {}
        self._authenticating = False
        self._transcript = SmtpTranscript()
        self._smtp = open_session(config, None)

    @property
    def description(self) -> str:
        """What errors call the other end: ``host:port``, or the process it runs."""
        return self._description

    @property
    def is_connected(self) -> bool:
        """Whether the session is still open."""
        return self._smtp.is_connected

    @property
    def uses_tls(self) -> bool:
        """Whether the open session is encrypted, from its first byte or after ``STARTTLS``."""
        if not self._smtp.is_connected:
            return False
        context: object = self._smtp.get_transport_info("sslcontext")  # pyright: ignore[reportAny] — aiosmtplib types transport info as Any
        return context is not None

    @property
    def has_pending_data(self) -> bool:
        """Whether the server sent more than the last reply, which the next command would read.

        A server closing the channel often queues a ``421`` behind its answer to a ``NOOP``.
        """
        protocol = self._smtp.protocol
        # aiosmtplib keeps what it received past a reply in a buffer it has no public reader
        # for; pinned below 6, as for the drain in _upload.drained.
        return protocol is not None and bool(protocol._buffer)  # noqa: SLF001 — see above  # pyright: ignore[reportPrivateUsage] — see above

    @property
    def capabilities(self) -> dict[str, list[str]]:
        """The extensions the last ``EHLO`` offered.

        Each extension's upper-cased keyword, mapped to its upper-cased parameters; empty
        before ``EHLO``, after ``STARTTLS`` and in a new session.
        """
        return dict(self._capabilities)

    def conceal(self, secret: str, identity: str = "") -> None:
        """Keep ``secret`` out of errors and the transcript; ``identity`` out of AUTH replies."""
        self._transcript.conceal(secret, identity)

    def take_transcript(self) -> str:
        """Return and forget the exchanges since the last call: ``> `` sent, ``< `` received."""
        return self._transcript.take()

    async def connect(self) -> str:
        """Connect to the configured server and return its greeting.

        Raises:
            UnexpectedResponseError: The server greeted with a code other than ``220``.
            TransportError: The server could not be reached, did not greet in time,
                or presented a certificate that is not the pinned one.
        """
        self.close()
        self._description = self._config.description
        self._smtp = open_session(self._config, None)
        greeting = await self._open()
        if self._config.tls:
            self._check_peer(unreachable(self._description, "peer fingerprint match failure"))
        return greeting

    async def connect_socket(self, sock: socket.socket, description: str) -> str:
        """Start a session over ``sock``, already connected, and return the greeting.

        The other end is typically a local sendmail speaking SMTP on its standard
        streams; ``description`` names it in errors. The session owns ``sock`` and
        closes it with the connection.
        """
        self.close()
        self._description = description
        self._smtp = open_session(self._config, sock)
        return await self._open()

    async def ehlo(self) -> str:
        """Greet with ``EHLO``, read the extensions the server offers, and return its reply."""
        reply = await self._exchange(f"EHLO {self._local_hostname}", (250,), self._smtp.ehlo)
        self._capabilities = parse_capabilities(reply)
        return reply

    async def starttls(self) -> None:
        """Switch the session to TLS; the server must be greeted again afterwards.

        Raises:
            UnexpectedResponseError: The server refused ``STARTTLS``.
            TransportError: The server does not offer it, the handshake failed, or the
                certificate is not the pinned one.
        """
        _ = await self._exchange("STARTTLS", (220,), lambda: upgrade(self._smtp, self.close))
        self._capabilities = {}
        self._check_peer("Unable to connect with STARTTLS: peer fingerprint match failure")

    async def execute(self, command: str, expected_codes: Sequence[int]) -> str:
        """Send ``command``, without its line ending, and return the reply.

        Authenticators drive their exchanges through this; while one is under way
        its lines are kept out of every error's ``debug``.

        Returns:
            The reply as the server sent it, its lines joined by CRLF.

        Raises:
            LogicError: ``expected_codes`` is empty.
            InvalidArgumentError: ``command`` contains a line break, or a character UTF-8
                cannot write.
            UnexpectedResponseError: The reply's code is not one of ``expected_codes``.
            TransportError: The connection was lost or the reply did not come in time.
        """
        return await self._exchange(
            command, expected_codes, lambda: self._smtp.execute_command(command.encode())
        )

    async def message(self, message: bytes) -> str:
        """Send ``message``, once ``DATA`` was accepted, and return the server's acceptance.

        Line endings become CRLF and a line starting with a period gets a second
        one, so no line of the message can end it early.
        """
        return await self._exchange(
            _MESSAGE, (250,), lambda: send_message(self._smtp, message, self._config.timeout)
        )

    def close(self) -> None:
        """Drop the connection without a word."""
        self._smtp.close()
        self._capabilities = {}
        self._authenticating = False

    @property
    def _local_hostname(self) -> str:
        return self._config.local_hostname.strip()

    async def _open(self) -> str:
        self._capabilities = {}
        self._authenticating = False
        self._transcript.reset()
        failed: MailerError
        try:
            greeting = await self._smtp.connect()
        except aiosmtplib.SMTPResponseException as error:
            failed = self._refused(None, (220,), response_of(error))
        except aiosmtplib.SMTPException as error:
            failed = failure(error, self._description)
        else:
            reply = render_reply(greeting.code, greeting.message)
            self._transcript.record(None, reply)
            return reply
        raise failed

    async def _exchange(
        self,
        command: str,
        expected_codes: Sequence[int],
        send: Callable[[], Awaitable[aiosmtplib.SMTPResponse]],
    ) -> str:
        """Send one command through ``send``, the way every command of the session goes.

        Raised once aiosmtplib's error is handled, ours has no context holding what it kept.
        """
        if not expected_codes:
            raise LogicError("You must set the expected response code.")
        starts_auth = command.partition(" ")[0].upper() == "AUTH"
        authenticating = self._authenticating or starts_auth
        shown = self._transcript.shown(command, authenticating=self._authenticating)
        failed: MailerError
        try:
            response = await send()
        except aiosmtplib.SMTPResponseException as error:
            self._authenticating = False
            failed = self._refused(shown, expected_codes, response_of(error), authenticating)
        except aiosmtplib.SMTPException as error:
            self._authenticating = False
            failed = failure(error, self._description)
            failed.append_debug(f"> {shown}\n")
        except UnicodeEncodeError:
            # The message would quote the character, which may be part of a credential.
            failed = InvalidArgumentError(
                "An SMTP command must only hold characters UTF-8 can write."
            )
        except ValueError as error:
            # aiosmtplib refuses a command that would smuggle a second one in.
            failed = InvalidArgumentError(str(error))
        else:
            self._authenticating = authenticating and response.code == _AUTH_CONTINUE
            if response.code not in expected_codes:
                raise self._refused(shown, expected_codes, response, authenticating)
            reply = render_reply(response.code, response.message)
            self._transcript.record(shown, reply, authenticating=authenticating)
            return reply
        raise failed

    def _check_peer(self, mismatch: str) -> None:
        """Close the session and raise ``mismatch`` unless the certificate is the pinned one."""
        fingerprint = self._config.peer_fingerprint
        if fingerprint is None:
            return
        try:
            matches = peer_matches(self._smtp, fingerprint)
        except aiosmtplib.SMTPException as error:
            # The server hung up before its certificate could be read.
            self.close()
            raise failure(error, self._description) from None
        if not matches:
            self.close()
            raise TransportError(mismatch)

    def _refused(
        self,
        shown: str | None,
        expected_codes: Sequence[int],
        response: aiosmtplib.SMTPResponse,
        authenticating: bool = False,
    ) -> UnexpectedResponseError:
        reply = self._transcript.scrub(
            render_reply(response.code, response.message), authenticating=authenticating
        )
        self._transcript.record(shown, reply)
        error = unexpected_response(expected_codes, response.code, reply)
        if shown is not None:
            error.append_debug(f"> {shown}\n")
        if reply:
            error.append_debug("".join(f"< {line}\n" for line in reply.split("\r\n")))
        return error
