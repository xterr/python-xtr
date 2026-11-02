"""The switch to TLS, and the certificate pinned by its fingerprint."""

from __future__ import annotations

import hashlib
import hmac
import ssl
from typing import TYPE_CHECKING

from xtr_mailer.exception import TransportError
from xtr_mailer.transport.smtp._smtp_connection_config import DIGEST_ALGORITHMS

if TYPE_CHECKING:
    from collections.abc import Callable

    import aiosmtplib

__all__ = ["peer_matches", "upgrade"]


async def upgrade(smtp: aiosmtplib.SMTP, close: Callable[[], None]) -> aiosmtplib.SMTPResponse:
    """Send ``STARTTLS`` on ``smtp`` and switch it to TLS; return the server's reply.

    Raises:
        TransportError: The handshake failed; ``close`` has been called.
    """
    try:
        return await smtp.starttls()
    except ssl.SSLError as error:
        close()
        raise TransportError(f"Unable to connect with STARTTLS: {error}") from None


def peer_matches(smtp: aiosmtplib.SMTP, fingerprint: str) -> bool:
    """Whether the certificate ``smtp``'s server presented has the digest ``fingerprint``.

    Raises:
        aiosmtplib.SMTPException: The server hung up before its certificate could be read.
    """
    ssl_object: object = smtp.get_transport_info("ssl_object")  # pyright: ignore[reportAny] — aiosmtplib types transport info as Any
    certificate = (
        ssl_object.getpeercert(binary_form=True) if isinstance(ssl_object, ssl.SSLObject) else None
    )
    algorithm = DIGEST_ALGORITHMS[len(fingerprint)]
    return certificate is not None and hmac.compare_digest(
        hashlib.new(algorithm, certificate, usedforsecurity=False).hexdigest(),
        fingerprint.lower(),
    )
