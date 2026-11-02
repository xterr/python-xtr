"""The settings an SMTP transport opens its next session with."""

from __future__ import annotations

import contextlib
import dataclasses
import ipaddress
import re
from typing import TYPE_CHECKING, Final

from xtr_mailer.exception import InvalidArgumentError

from ._smtp_connection_config import SmtpConnectionConfig

if TYPE_CHECKING:
    from typing import Self

__all__ = ["SmtpConnectionSettings"]

_CONTROL_CHARACTERS: Final = re.compile(r"[\x00-\x1f\x7f]")
_SMTP_PORT: Final = 25
_SMTPS_PORT: Final = 465


class SmtpConnectionSettings:
    """Where a transport's sessions connect, and how: the local domain, timeout, peer checks.

    A setting changed while a session is open applies to the next one. The transport replaces
    the class's default configuration with its server's in its constructor.
    """

    _config: SmtpConnectionConfig = SmtpConnectionConfig()

    def _server_name(self) -> str:
        """Name it ``smtp://host``, ``smtps://`` over TLS, with the port unless the default."""
        config = self._config
        name = f"smtp{'s' if config.tls else ''}://{config.host}"
        if not (config.port == _SMTP_PORT or (config.tls and config.port == _SMTPS_PORT)):
            name += f":{config.port}"
        return name

    def set_local_domain(self, domain: str) -> Self:
        """Name the client ``domain`` in ``HELO``: its fully qualified name, else its address.

        An address is bracketed as RFC 5321 writes it: ``[192.0.2.1]``, ``[IPv6:2001:db8::1]``.

        Raises:
            InvalidArgumentError: ``domain`` holds a control character.
        """
        if _CONTROL_CHARACTERS.search(domain):
            raise InvalidArgumentError("The local domain name must not contain control characters.")
        if domain and not domain.startswith("["):
            with contextlib.suppress(ValueError):
                address = ipaddress.ip_address(domain)
                ipv6 = isinstance(address, ipaddress.IPv6Address)
                domain = f"[IPv6:{domain}]" if ipv6 else f"[{domain}]"
        self._config = dataclasses.replace(self._config, local_hostname=domain)
        return self

    def get_local_domain(self) -> str:
        """Return the name ``HELO`` gives, bracketed when it is an address."""
        return self._config.local_hostname

    def set_timeout(self, seconds: float) -> Self:
        """Wait at most ``seconds`` to connect and for each reply; 60 by default."""
        self._config = dataclasses.replace(self._config, timeout=float(seconds))
        return self

    def get_timeout(self) -> float:
        """Return how long a connection and each reply are waited for, in seconds."""
        return self._config.timeout

    def set_verify_peer(self, verify: bool) -> Self:
        """Check the server's certificate and name over TLS, as by default; ``False`` trusts any."""
        self._config = dataclasses.replace(self._config, validate_certs=verify)
        return self

    def is_peer_verified(self) -> bool:
        """Return whether the server's certificate is checked."""
        return self._config.validate_certs

    def set_peer_fingerprint(self, fingerprint: str | None) -> Self:
        """Accept over TLS only the certificate with this MD5, SHA-1 or SHA-256 digest, in hex.

        Raises:
            InvalidArgumentError: ``fingerprint`` is no such digest.
        """
        self._config = dataclasses.replace(self._config, peer_fingerprint=fingerprint)
        return self
