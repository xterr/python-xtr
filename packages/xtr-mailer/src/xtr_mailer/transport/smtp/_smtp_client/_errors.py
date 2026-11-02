"""What aiosmtplib raises, told as the errors the transports read."""

from __future__ import annotations

from typing import Final

import aiosmtplib

from xtr_mailer.exception import TransportError

__all__ = ["failure", "response_of", "unreachable"]

_MALFORMED_LINE: Final = "Malformed SMTP response line: "


def failure(error: aiosmtplib.SMTPException, description: str) -> TransportError:
    """Return the error a connection to ``description`` that failed with ``error`` is.

    A server that cannot be reached, one that went silent and one that hung up are each
    named as such; anything else keeps aiosmtplib's message.
    """
    cause = error.__cause__
    match error:
        case aiosmtplib.SMTPConnectTimeoutError() if not isinstance(
            cause, aiosmtplib.SMTPTimeoutError
        ):
            return TransportError(unreachable(description, error.message))
        case aiosmtplib.SMTPTimeoutError():
            return TransportError(f'Connection to "{description}" timed out.')
        case aiosmtplib.SMTPConnectError() if not isinstance(
            cause, aiosmtplib.SMTPServerDisconnected
        ):
            return TransportError(
                unreachable(description, str(cause) if cause is not None else error.message)
            )
        case aiosmtplib.SMTPServerDisconnected() | aiosmtplib.SMTPConnectError():
            return TransportError(f'Connection to "{description}" has been closed unexpectedly.')
        case _:
            return TransportError(error.message)


def unreachable(description: str, reason: str) -> str:
    """Say the server ``description`` names could not be reached, and why."""
    return f'Connection could not be established with host "{description}": {reason}'


def response_of(error: aiosmtplib.SMTPResponseException) -> aiosmtplib.SMTPResponse:
    """The reply aiosmtplib raised over; one it could not parse has code ``-1``.

    An unparsable line is given back as the server sent it, trimmed, not wrapped in
    aiosmtplib's explanation.
    """
    message = error.message
    if error.code <= 0:
        message = message.removeprefix(_MALFORMED_LINE).strip()
    return aiosmtplib.SMTPResponse(error.code, message)
