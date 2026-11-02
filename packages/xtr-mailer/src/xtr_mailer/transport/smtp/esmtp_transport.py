"""Email handed to a mail server over ESMTP: extensions, TLS and authentication."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Final

from typing_extensions import override

from xtr_mailer.exception import TransportError, UnexpectedResponseError

from .auth import (
    CramMd5Authenticator,
    LoginAuthenticator,
    PlainAuthenticator,
    XOAuth2Authenticator,
)
from .smtp_transport import SmtpTransport

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from typing import Self

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_logging_contracts import LoggerInterface

    from .auth import AuthenticatorInterface

__all__ = ["EsmtpTransport"]

_SMTPS_PORT: Final = 465
_NO_AUTHENTICATOR: Final = 504
_AUTHENTICATION_FAILED: Final = 535


class EsmtpTransport(SmtpTransport):
    """Greets with ``EHLO``, switches to TLS when it can, and logs in when given a user.

    ``EHLO`` reads the extensions the server offers; a server refusing it is greeted with
    ``HELO`` instead. When the server offers ``STARTTLS`` on a plain session, the session
    switches to TLS and greets again, unless :meth:`set_auto_tls` turned that off;
    :meth:`set_require_tls` refuses to go on without TLS. With a user set and ``AUTH``
    offered, each authenticator whose mechanism the server lists is tried in turn — by
    default ``CRAM-MD5``, ``PLAIN``, ``LOGIN``, ``XOAUTH2``, roughly the safest first — the
    session reset after each refusal. A non-ASCII local part goes out only to a server
    offering ``SMTPUTF8``.

    Neither the user nor the password is ever shown: not in its name, an error or a log.
    """

    def __init__(  # noqa: PLR0913 — the server's address, the collaborators, the mechanisms
        self,
        host: str = "localhost",
        port: int = 0,
        tls: bool | None = None,
        *,
        event_dispatcher: EventDispatcherInterface | None = None,
        logger: LoggerInterface | None = None,
        clock: ClockInterface | None = None,
        authenticators: Iterable[AuthenticatorInterface] | None = None,
    ) -> None:
        """Prepare a session with ``host``; nothing connects until an email is sent.

        Args:
            host: The server's name or address.
            port: The server's port; ``0`` picks 465 over TLS, else 25.
            tls: Speak TLS from the first byte. ``None`` decides from the port: on 465, or
                when no port is given and the host is not ``localhost``.
            event_dispatcher: Where the email events go; ``None`` announces nothing.
            logger: Where the session's start and end are logged.
            clock: What the ping threshold, the restart sleep and the pace are measured on.
            authenticators: The mechanisms to log in with, in the order to try them;
                ``None`` for the four built in.
        """
        if tls is None:
            tls = port == _SMTPS_PORT or (port == 0 and host != "localhost")
        if port == 0:
            port = _SMTPS_PORT if tls else 25
        super().__init__(
            host, port, tls, event_dispatcher=event_dispatcher, logger=logger, clock=clock
        )
        self._authenticators: list[AuthenticatorInterface] = []
        self.set_authenticators(
            authenticators
            if authenticators is not None
            else [
                CramMd5Authenticator(),
                PlainAuthenticator(),
                LoginAuthenticator(),
                XOAuth2Authenticator(),
            ]
        )
        self._username: str = ""
        self._password: str = ""
        self._capabilities: dict[str, list[str]] = {}
        self._auto_tls: bool = True
        self._require_tls: bool = False

    def set_username(self, username: str) -> Self:
        """Log in as ``username``; empty, as by default, logs in as no one."""
        self._username = username
        return self

    def get_username(self) -> str:
        """Return the user to log in as."""
        return self._username

    def set_password(self, password: str) -> Self:
        """Log in with ``password`` — an access token for ``XOAUTH2``."""
        self._password = password
        return self

    def get_password(self) -> str:
        """Return the password to log in with."""
        return self._password

    def set_auto_tls(self, auto_tls: bool) -> Self:
        """Switch a plain session to TLS when the server offers ``STARTTLS``, as by default."""
        self._auto_tls = auto_tls
        return self

    def is_auto_tls(self) -> bool:
        """Return whether a plain session switches to TLS when it can."""
        return self._auto_tls

    def set_require_tls(self, require_tls: bool) -> Self:
        """Refuse to send over a session that is not encrypted."""
        self._require_tls = require_tls
        return self

    def is_tls_required(self) -> bool:
        """Return whether a session must be encrypted."""
        return self._require_tls

    def set_authenticators(self, authenticators: Iterable[AuthenticatorInterface]) -> None:
        """Log in with ``authenticators``, tried in this order, instead of the ones set."""
        self._authenticators = list(authenticators)

    def add_authenticator(self, authenticator: AuthenticatorInterface) -> None:
        """Try ``authenticator`` after the ones set."""
        self._authenticators.append(authenticator)

    @override
    async def execute_command(self, command: str, codes: Sequence[int]) -> str:
        """Send ``command``; the session's ``HELO`` becomes ``EHLO``, TLS and login."""
        if list(codes) == [250] and command.startswith("HELO "):
            return await self._do_ehlo_command()
        return await super().execute_command(command, codes)

    def _get_capabilities(self) -> dict[str, list[str]]:
        """Return the extensions the server offers this session, as ``EHLO`` listed them."""
        return dict(self._capabilities)

    @override
    def _server_supports_smtp_utf8(self) -> bool:
        return "SMTPUTF8" in self._capabilities

    async def _do_ehlo_command(self) -> str:
        client = self._client
        self._capabilities = {}
        try:
            reply = await client.ehlo()
        except TransportError as error:
            try:
                return await super().execute_command(f"HELO {self.get_local_domain()}", [250])
            except TransportError as helo_error:
                # A HELO that got no reply says less than the EHLO error before it.
                if not helo_error.code:
                    raise error from None
                raise
        self._capabilities = client.capabilities
        tls_started = client.uses_tls
        if self._auto_tls and not tls_started and "STARTTLS" in self._capabilities:
            await client.starttls()
            tls_started = True
            reply = await client.ehlo()
            self._capabilities = client.capabilities
        if not tls_started and self._require_tls:
            raise TransportError("TLS required but neither TLS or STARTTLS are in use.")
        if "AUTH" in self._capabilities:
            await self._handle_auth(self._capabilities["AUTH"])
        return reply

    async def _handle_auth(self, modes: list[str]) -> None:
        if not self._username:
            return
        self._client.conceal(self._password, self._username)
        offered = [mode.lower() for mode in modes]
        code = 0
        tried: list[str] = []
        errors: dict[str, str] = {}
        for authenticator in self._authenticators:
            keyword = authenticator.get_auth_keyword()
            if keyword.lower() not in offered:
                continue
            code = 0
            tried.append(keyword)
            try:
                await authenticator.authenticate(self)
            except UnexpectedResponseError as error:
                code = error.code
                # The refusal was probably final; the next authenticator will tell.
                with contextlib.suppress(TransportError):
                    _ = await self.execute_command("RSET", [250])
                errors[keyword] = str(error)
            else:
                return
        if not tried:
            supported = '", "'.join(offered)
            raise TransportError(
                "Failed to find an authenticator supported by the SMTP server, which currently "
                f'supports: "{supported}".',
                code or _NO_AUTHENTICATOR,
            )
        names = '", "'.join(tried)
        message = (
            f'Failed to authenticate on SMTP server using the following authenticators: "{names}".'
        )
        message += "".join(
            f' Authenticator "{name}" returned "{text}".' for name, text in errors.items()
        )
        raise TransportError(message, code or _AUTHENTICATION_FAILED)
