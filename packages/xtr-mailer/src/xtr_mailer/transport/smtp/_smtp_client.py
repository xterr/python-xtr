"""One SMTP session, driven command by command — the only module that imports aiosmtplib.

aiosmtplib speaks the protocol: it connects, switches to TLS and reads replies.
Everything it raises is turned here into a :class:`TransportError` or an
:class:`UnexpectedResponseError`, so the transports built on this client never
see one of its types.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import ssl
from asyncio import wait_for
from typing import TYPE_CHECKING, Final, final

import aiosmtplib

from xtr_mailer.exception import (
    InvalidArgumentError,
    LogicError,
    TransportError,
    UnexpectedResponseError,
)

from ._smtp_connection_config import DIGEST_ALGORITHMS
from ._smtp_reply import render_reply, unexpected_response
from ._smtp_transcript import REDACTED, SmtpTranscript

if TYPE_CHECKING:
    import socket
    from collections.abc import Awaitable, Callable, Sequence

    from aiosmtplib.protocol import SMTPProtocol

    from ._smtp_connection_config import SmtpConnectionConfig

__all__ = ["SmtpClient"]

_CAPABILITY: Final = re.compile(r"[0-9]{3}[ -]([A-Z0-9-]+)((?:[ =].*)?)", re.IGNORECASE)
_LINE_ENDINGS: Final = re.compile(rb"\r\n|\r|\n")
_LEADING_PERIOD: Final = re.compile(rb"(?m)^\.")
_SERVICE_CLOSING: Final = 421
_AUTH_CONTINUE: Final = 334
_MESSAGE: Final = "[message]"
_CHUNK_SIZE: Final = 64 * 1024
_MALFORMED_LINE: Final = "Malformed SMTP response line: "


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
        self._smtp = self._session(None)

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
        # for; pinned below 6, as for the drain in _drained.
        return protocol is not None and bool(protocol._buffer)  # noqa: SLF001 — see above  # pyright: ignore[reportPrivateUsage] — see above

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
        self._smtp = self._session(None)
        greeting = await self._open()
        if self._config.tls:
            self._check_peer(self._unreachable("peer fingerprint match failure"))
        return greeting

    async def connect_socket(self, sock: socket.socket, description: str) -> str:
        """Start a session over ``sock``, already connected, and return the greeting.

        The other end is typically a local sendmail speaking SMTP on its standard
        streams; ``description`` names it in errors. The session owns ``sock`` and
        closes it with the connection.
        """
        self.close()
        self._description = description
        self._smtp = self._session(sock)
        return await self._open()

    @property
    def capabilities(self) -> dict[str, list[str]]:
        """The extensions the last ``EHLO`` offered.

        Each extension's upper-cased keyword, mapped to its upper-cased parameters; empty
        before ``EHLO``, after ``STARTTLS`` and in a new session.
        """
        return dict(self._capabilities)

    async def ehlo(self) -> str:
        """Greet with ``EHLO``, read the extensions the server offers, and return its reply."""
        reply = await self._exchange(f"EHLO {self._local_hostname}", (250,), self._smtp.ehlo)
        capabilities: dict[str, list[str]] = {}
        for line in reply.split("\r\n")[1:]:
            if found := _CAPABILITY.fullmatch(line):
                parameters = str(found.group(2)).lstrip(" =").upper()
                capabilities[str(found.group(1)).upper()] = (
                    parameters.split(" ") if parameters else []
                )
        self._capabilities = capabilities
        return reply

    async def helo(self) -> str:
        """Greet with ``HELO``, for a server that offers no extensions."""
        return await self._exchange(f"HELO {self._local_hostname}", (250,), self._smtp.helo)

    def supports_extension(self, extension: str) -> bool:
        """Whether the last ``EHLO`` offered ``extension``, compared case-insensitively."""
        return extension.upper() in self._capabilities

    async def starttls(self) -> None:
        """Switch the session to TLS; the server must be greeted again afterwards.

        Raises:
            UnexpectedResponseError: The server refused ``STARTTLS``.
            TransportError: The server does not offer it, the handshake failed, or the
                certificate is not the pinned one.
        """
        _ = await self._exchange("STARTTLS", (220,), self._upgrade)
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

    async def mail_from(self, address: str, options: Sequence[str] = ()) -> str:
        """Open an envelope from ``address``; ``options`` follow it (``SMTPUTF8``)."""
        return await self.execute(" ".join([f"MAIL FROM:<{address}>", *options]), (250,))

    async def rcpt_to(self, address: str) -> str:
        """Add ``address`` to the envelope's recipients."""
        return await self.execute(f"RCPT TO:<{address}>", (250, 251, 252))

    async def data(self, message: bytes) -> str:
        """Send ``message`` after ``DATA`` and return the server's acceptance.

        Returns:
            The reply accepting the message, which may name the id it was queued as.
        """
        _ = await self.execute("DATA", (354,))
        return await self.message(message)

    async def message(self, message: bytes) -> str:
        """Send ``message``, once ``DATA`` was accepted, and return the server's acceptance.

        Line endings become CRLF and a line starting with a period gets a second
        one, so no line of the message can end it early.
        """
        return await self._exchange(_MESSAGE, (250,), lambda: self._send_message(message))

    async def noop(self) -> str:
        """Check the session is alive."""
        return await self.execute("NOOP", (250,))

    async def rset(self) -> str:
        """Abandon the envelope under way."""
        return await self.execute("RSET", (250,))

    async def quit(self) -> None:
        """End the session politely; the connection is closed whatever the reply."""
        try:
            _ = await self.execute("QUIT", (221,))
        finally:
            self.close()

    def close(self) -> None:
        """Drop the connection without a word."""
        self._smtp.close()
        self._capabilities = {}
        self._authenticating = False

    @property
    def _local_hostname(self) -> str:
        return self._config.local_hostname.strip()

    def _session(self, sock: socket.socket | None) -> aiosmtplib.SMTP:
        config = self._config
        source = config.source_address
        try:
            return aiosmtplib.SMTP(
                hostname=None if sock is not None else config.host.strip("[]"),
                port=None if sock is not None else config.port,
                local_hostname=config.local_hostname,
                source_address=(source.strip("[]"), 0) if source is not None else None,
                timeout=config.timeout,
                use_tls=config.tls and sock is None,
                start_tls=False,
                validate_certs=config.validate_certs,
                sock=sock,
            )
        except ValueError as error:
            raise InvalidArgumentError(str(error)) from None

    async def _open(self) -> str:
        self._capabilities = {}
        self._authenticating = False
        self._transcript.reset()
        try:
            greeting = await self._smtp.connect()
        except aiosmtplib.SMTPResponseException as error:
            raise self._refused(None, (220,), _response(error)) from None
        except aiosmtplib.SMTPException as error:
            raise self._failure(error) from None
        reply = render_reply(greeting.code, greeting.message)
        self._transcript.record(None, reply)
        return reply

    async def _exchange(
        self,
        command: str,
        expected_codes: Sequence[int],
        send: Callable[[], Awaitable[aiosmtplib.SMTPResponse]],
    ) -> str:
        if not expected_codes:
            raise LogicError("You must set the expected response code.")
        starts_auth = command.partition(" ")[0].upper() == "AUTH"
        authenticating = self._authenticating or starts_auth
        shown = self._shown(command)
        try:
            response = await send()
        except aiosmtplib.SMTPResponseException as error:
            self._authenticating = False
            raise self._refused(shown, expected_codes, _response(error), authenticating) from None
        except aiosmtplib.SMTPException as error:
            self._authenticating = False
            failure = self._failure(error)
            failure.append_debug(f"> {shown}\n")
            raise failure from None
        except UnicodeEncodeError:
            # The message would quote the character, which may be part of a credential.
            raise InvalidArgumentError(
                "An SMTP command must only hold characters UTF-8 can write."
            ) from None
        except ValueError as error:
            # aiosmtplib refuses a command that would smuggle a second one in.
            raise InvalidArgumentError(str(error)) from None
        self._authenticating = authenticating and response.code == _AUTH_CONTINUE
        if response.code not in expected_codes:
            raise self._refused(shown, expected_codes, response, authenticating)
        reply = render_reply(response.code, response.message)
        self._transcript.record(shown, reply, authenticating=authenticating)
        return reply

    async def _upgrade(self) -> aiosmtplib.SMTPResponse:
        try:
            return await self._smtp.starttls()
        except ssl.SSLError as error:
            self.close()
            raise TransportError(f"Unable to connect with STARTTLS: {error}") from None

    async def _send_message(self, message: bytes) -> aiosmtplib.SMTPResponse:
        protocol = self._smtp.protocol
        if protocol is None:
            raise aiosmtplib.SMTPServerDisconnected("Connection lost")
        content = _LINE_ENDINGS.sub(b"\r\n", message)
        if not content.endswith(b"\r\n"):
            content += b"\r\n"
        payload = memoryview(_LEADING_PERIOD.sub(b"..", content) + b".\r\n")
        try:
            # The timeout bounds each write, not the whole upload: a slow server still
            # reading a large message is healthy, one that stops reading is not. Only
            # the writes before the last are waited for: aiosmtplib drops a reply that
            # arrives while no read is pending, so nothing may yield between the final
            # write and read_response, which marks its read pending before it awaits.
            for start in range(0, len(payload), _CHUNK_SIZE):
                if start:
                    await self._drained(protocol)
                protocol.write(bytes(payload[start : start + _CHUNK_SIZE]))
            response = await protocol.read_response(timeout=self._config.timeout)
        except (aiosmtplib.SMTPServerDisconnected, aiosmtplib.SMTPTimeoutError):
            self._smtp.close()
            raise
        if response.code == _SERVICE_CLOSING:
            self._smtp.close()
        return response

    async def _drained(self, protocol: SMTPProtocol) -> None:
        """Wait until the connection has taken what was written, within the timeout."""
        try:
            # aiosmtplib's protocol has flow control but no public drain; pinned below 6.
            # Polling the transport's write buffer instead would trade this wake-up on
            # resume, and the error on a lost connection, for a sleep interval.
            await wait_for(protocol._drain_helper(), self._config.timeout)  # noqa: SLF001 — see above  # pyright: ignore[reportPrivateUsage] — see above
        except TimeoutError:
            raise aiosmtplib.SMTPTimeoutError("Timed out writing the message") from None
        except OSError:
            # A lost connection, or a TLS layer that failed (ssl.SSLError).
            raise aiosmtplib.SMTPServerDisconnected("Connection lost") from None

    def _check_peer(self, mismatch: str) -> None:
        """Close the session and raise ``mismatch`` unless the certificate is the pinned one."""
        fingerprint = self._config.peer_fingerprint
        if fingerprint is None:
            return
        try:
            ssl_object: object = self._smtp.get_transport_info("ssl_object")  # pyright: ignore[reportAny] — aiosmtplib types transport info as Any
        except aiosmtplib.SMTPException as error:
            # The server hung up before its certificate could be read.
            self.close()
            raise self._failure(error) from None
        certificate = (
            ssl_object.getpeercert(binary_form=True)
            if isinstance(ssl_object, ssl.SSLObject)
            else None
        )
        algorithm = DIGEST_ALGORITHMS[len(fingerprint)]
        if certificate is None or not hmac.compare_digest(
            hashlib.new(algorithm, certificate, usedforsecurity=False).hexdigest(),
            fingerprint.lower(),
        ):
            self.close()
            raise TransportError(mismatch)

    def _shown(self, command: str) -> str:
        if self._authenticating:
            self._transcript.learn(command)
            return REDACTED
        verb, _, rest = command.partition(" ")
        mechanism, _, credentials = rest.partition(" ")
        if verb.upper() == "AUTH" and credentials:
            self._transcript.learn(credentials)
            return f"{verb} {mechanism} {REDACTED}"
        return command

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

    def _failure(self, error: aiosmtplib.SMTPException) -> TransportError:
        cause = error.__cause__
        match error:
            case aiosmtplib.SMTPConnectTimeoutError() if not isinstance(
                cause, aiosmtplib.SMTPTimeoutError
            ):
                return TransportError(self._unreachable(error.message))
            case aiosmtplib.SMTPTimeoutError():
                return TransportError(f'Connection to "{self._description}" timed out.')
            case aiosmtplib.SMTPConnectError() if not isinstance(
                cause, aiosmtplib.SMTPServerDisconnected
            ):
                return TransportError(
                    self._unreachable(str(cause) if cause is not None else error.message)
                )
            case aiosmtplib.SMTPServerDisconnected() | aiosmtplib.SMTPConnectError():
                return TransportError(
                    f'Connection to "{self._description}" has been closed unexpectedly.'
                )
            case _:
                return TransportError(error.message)

    def _unreachable(self, reason: str) -> str:
        return f'Connection could not be established with host "{self._description}": {reason}'


def _response(error: aiosmtplib.SMTPResponseException) -> aiosmtplib.SMTPResponse:
    """The reply aiosmtplib raised over; one it could not parse has code ``-1``.

    An unparsable line is given back as the server sent it, trimmed, not wrapped in
    aiosmtplib's explanation.
    """
    message = error.message
    if error.code <= 0:
        message = message.removeprefix(_MALFORMED_LINE).strip()
    return aiosmtplib.SMTPResponse(error.code, message)
