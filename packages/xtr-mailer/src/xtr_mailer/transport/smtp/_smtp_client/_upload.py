"""A message written after ``DATA``, and the reply that accepts or refuses it."""

from __future__ import annotations

import re
from asyncio import wait_for
from typing import TYPE_CHECKING, Final

import aiosmtplib

if TYPE_CHECKING:
    from aiosmtplib.protocol import SMTPProtocol

__all__ = ["drained", "send_message"]

_LINE_ENDINGS: Final = re.compile(rb"\r\n|\r|\n")
_LEADING_PERIOD: Final = re.compile(rb"(?m)^\.")
_SERVICE_CLOSING: Final = 421
_CHUNK_SIZE: Final = 64 * 1024


async def send_message(
    smtp: aiosmtplib.SMTP, message: bytes, seconds: float
) -> aiosmtplib.SMTPResponse:
    """Write ``message`` on ``smtp`` and return the reply that ends it.

    Line endings become CRLF and a line starting with a period gets a second one, so no
    line of the message can end it early. Each write and the reply are waited for at most
    ``seconds``. A lost connection, a timeout or a ``421`` closes ``smtp``.
    """
    protocol = smtp.protocol
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
                await drained(protocol, seconds)
            protocol.write(bytes(payload[start : start + _CHUNK_SIZE]))
        response = await protocol.read_response(timeout=seconds)
    except (aiosmtplib.SMTPServerDisconnected, aiosmtplib.SMTPTimeoutError):
        smtp.close()
        raise
    if response.code == _SERVICE_CLOSING:
        smtp.close()
    return response


async def drained(protocol: SMTPProtocol, seconds: float) -> None:
    """Wait until the connection has taken what was written, within ``seconds``."""
    try:
        # aiosmtplib's protocol has flow control but no public drain; pinned below 6.
        # Polling the transport's write buffer instead would trade this wake-up on
        # resume, and the error on a lost connection, for a sleep interval.
        await wait_for(protocol._drain_helper(), seconds)  # noqa: SLF001 — see above  # pyright: ignore[reportPrivateUsage] — see above
    except TimeoutError:
        raise aiosmtplib.SMTPTimeoutError("Timed out writing the message") from None
    except OSError:
        # A lost connection, or a TLS layer that failed (ssl.SSLError).
        raise aiosmtplib.SMTPServerDisconnected("Connection lost") from None
