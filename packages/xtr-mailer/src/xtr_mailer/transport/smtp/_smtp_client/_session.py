"""An aiosmtplib session made from a connection's settings, and the extensions it is offered."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

import aiosmtplib

from xtr_mailer.exception import InvalidArgumentError, TransportError

from ._errors import unreachable

if TYPE_CHECKING:
    import socket

    from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig

__all__ = ["greet", "open_session", "parse_capabilities"]

_CAPABILITY: Final = re.compile(r"[0-9]{3}[ -]([A-Z0-9-]+)((?:[ =].*)?)", re.IGNORECASE)


def open_session(config: SmtpConnectionConfig, sock: socket.socket | None) -> aiosmtplib.SMTP:
    """Return a session to the configured server, or over ``sock``; nothing connects yet.

    Raises:
        InvalidArgumentError: The local hostname has whitespace or control characters.
    """
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


async def greet(smtp: aiosmtplib.SMTP, description: str) -> aiosmtplib.SMTPResponse:
    """Connect ``smtp`` to its server, ``description`` in errors, and return the greeting.

    Raises:
        TransportError: The resolver could not look the host name up.
        aiosmtplib.SMTPException: The server could not be reached, or greeted badly.
    """
    try:
        greeting = await smtp.connect()
    except ValueError:
        # The resolver refuses a name it cannot encode with a UnicodeError, which aiosmtplib
        # lets through, having closed the session; its text quotes the name, so it is dropped.
        pass
    else:
        return greeting
    raise TransportError(unreachable(description, "the resolver cannot look the host name up."))


def parse_capabilities(reply: str) -> dict[str, list[str]]:
    """Return the extensions an ``EHLO`` reply lists, keywords and parameters upper-cased.

    The first line greets; a line that names no extension is skipped.
    """
    capabilities: dict[str, list[str]] = {}
    for line in reply.split("\r\n")[1:]:
        if found := _CAPABILITY.fullmatch(line):
            parameters = str(found.group(2)).lstrip(" =").upper()
            capabilities[str(found.group(1)).upper()] = parameters.split(" ") if parameters else []
    return capabilities
