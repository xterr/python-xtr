"""Where an SMTP client connects, and how it secures the connection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, final

from xtr_mailer.exception import InvalidArgumentError

__all__ = ["DIGEST_ALGORITHMS", "SmtpConnectionConfig"]

DIGEST_ALGORITHMS: Final = {32: "md5", 40: "sha1", 64: "sha256"}
"""The digest a peer fingerprint is taken with, told apart by its length in hex digits."""

_HEX_DIGITS: Final = re.compile(r"[0-9a-fA-F]+")


@final
@dataclass(frozen=True, slots=True)
class SmtpConnectionConfig:
    """The settings of one SMTP connection.

    Attributes:
        host: The server's name or address; a literal IPv6 address may be bracketed.
        port: The server's port.
        tls: Speak TLS from the first byte, rather than switching with ``STARTTLS``.
        timeout: Seconds to wait for the connection and for each reply.
        local_hostname: The name the client gives itself in ``EHLO`` and ``HELO``.
        source_address: The local address the connection leaves from; the system's
            choice when ``None``.
        validate_certs: Check the server's certificate against the system's trusted
            authorities and its name against :attr:`host`.
        peer_fingerprint: The digest, in hex, the server's certificate must have —
            MD5, SHA-1 or SHA-256, told apart by length. Pins one certificate,
            whether or not it is otherwise trusted.
    """

    host: str = "localhost"
    port: int = 25
    tls: bool = False
    timeout: float = 60.0
    local_hostname: str = "[127.0.0.1]"
    source_address: str | None = None
    validate_certs: bool = True
    peer_fingerprint: str | None = None

    def __post_init__(self) -> None:
        """Refuse a fingerprint no digest could produce, before anything connects."""
        fingerprint = self.peer_fingerprint
        if fingerprint is not None and (
            len(fingerprint) not in DIGEST_ALGORITHMS or not _HEX_DIGITS.fullmatch(fingerprint)
        ):
            raise InvalidArgumentError(
                f'The peer fingerprint "{fingerprint}" is not an MD5, SHA-1 or SHA-256 digest '
                "in hex."
            )

    @property
    def description(self) -> str:
        """The server as errors name it: ``host:port``, prefixed ``ssl://`` for TLS."""
        return f"{'ssl://' if self.tls else ''}{self.host}:{self.port}"
