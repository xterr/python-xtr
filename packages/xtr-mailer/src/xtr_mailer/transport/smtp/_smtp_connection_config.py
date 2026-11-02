"""Where an SMTP client connects, and how it secures the connection."""

from __future__ import annotations

import ipaddress
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Final, final

from xtr_mailer.exception import InvalidArgumentError

__all__ = ["DIGEST_ALGORITHMS", "SmtpConnectionConfig", "is_digest", "is_ip_address"]

DIGEST_ALGORITHMS: Final = {32: "md5", 40: "sha1", 64: "sha256"}
"""The digest a peer fingerprint is taken with, told apart by its length in hex digits."""

_HEX_DIGITS: Final = re.compile(r"[0-9a-fA-F]+")
_MAX_PORT: Final = 65535
# Control and format characters, line and paragraph separators: none names a server, and each
# would reach the resolver, a log line or an error as something the host does not say.
_CONTROL_CATEGORIES: Final = frozenset({"Cc", "Cf", "Zl", "Zp"})


def is_digest(fingerprint: str) -> bool:
    """Tell whether ``fingerprint`` is an MD5, SHA-1 or SHA-256 digest written in hex."""
    return len(fingerprint) in DIGEST_ALGORITHMS and _HEX_DIGITS.fullmatch(fingerprint) is not None


def is_ip_address(address: str) -> bool:
    """Tell whether ``address`` is an IPv4 or an IPv6 address, the IPv6 one maybe bracketed."""
    bracketed = address.startswith("[") and address.endswith("]")
    try:
        parsed = ipaddress.ip_address(address[1:-1] if bracketed else address)
    except ValueError:
        return False
    return isinstance(parsed, ipaddress.IPv6Address) or not bracketed


@final
@dataclass(frozen=True, slots=True)
class SmtpConnectionConfig:
    """The settings of one SMTP connection.

    Attributes:
        host: The server's name or address; a literal IPv6 address may be bracketed. A
            control, format or line-separating character is refused.
        port: The server's port, from 1 to 65535.
        tls: Speak TLS from the first byte, rather than switching with ``STARTTLS``.
        timeout: Seconds to wait for the connection and for each reply; positive and finite,
            as an infinite or undefined one would wait forever.
        local_hostname: The name the client gives itself in ``EHLO`` and ``HELO``.
        source_address: The local IP address the connection leaves from, an IPv6 one maybe
            bracketed; the system's choice when ``None``.
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
        """Refuse a setting no connection could be made with, before anything connects."""
        if any(unicodedata.category(character) in _CONTROL_CATEGORIES for character in self.host):
            raise InvalidArgumentError("The SMTP host name must not contain control characters.")
        if not 0 < self.port <= _MAX_PORT:
            raise InvalidArgumentError(
                f'The SMTP port must be between 1 and {_MAX_PORT}, "{self.port}" given.'
            )
        if not (math.isfinite(self.timeout) and self.timeout > 0):
            raise InvalidArgumentError(
                f'The SMTP timeout must be a positive number of seconds, "{self.timeout}" given.'
            )
        if self.source_address is not None and not is_ip_address(self.source_address):
            raise InvalidArgumentError("The source IP must be an IPv4 or IPv6 address.")
        fingerprint = self.peer_fingerprint
        if fingerprint is not None and not is_digest(fingerprint):
            raise InvalidArgumentError(
                f'The peer fingerprint "{fingerprint}" is not an MD5, SHA-1 or SHA-256 digest '
                "in hex."
            )

    @property
    def description(self) -> str:
        """The server as errors name it: ``host:port``, prefixed ``ssl://`` for TLS."""
        return f"{'ssl://' if self.tls else ''}{self.host}:{self.port}"
