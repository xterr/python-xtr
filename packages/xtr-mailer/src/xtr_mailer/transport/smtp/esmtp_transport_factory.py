"""Builds ESMTP transports from ``smtp://`` and ``smtps://`` DSNs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_mailer.exception import UnsupportedSchemeError
from xtr_mailer.transport.abstract_transport_factory import AbstractTransportFactory

from ._esmtp_dsn_options import read_count, read_flag, read_number, read_text, refusal
from ._smtp_connection_config import is_digest, is_ip_address
from .esmtp_transport import EsmtpTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_mailer.transport.dsn import Dsn

__all__ = ["EsmtpTransportFactory"]

_SECONDS: Final = "a number of seconds, zero or more"
_ADDRESS: Final = "an IPv4 or IPv6 address"
_DIGEST: Final = "an MD5, SHA-1 or SHA-256 digest in hex"
_DOMAIN: Final = "a domain name or an address"


@final
class EsmtpTransportFactory(AbstractTransportFactory):
    """Builds an :class:`EsmtpTransport` for ``smtp://`` and ``smtps://``.

    ``smtps`` speaks TLS from the first byte, on 465 unless the DSN names a port. ``smtp``
    switches to TLS with ``STARTTLS`` when the server offers it; with no port it goes to 465
    over TLS for any host but ``localhost``, which it reaches on 25 — on 25 for every host
    with ``auto_tls`` off. The user and the password of the DSN log in. The options:

    - ``auto_tls`` — ``false`` keeps an ``smtp`` session plain, even on a server offering
      ``STARTTLS``; ``require_tls`` refuses to send over a session that is not encrypted.
    - ``verify_peer`` — ``false`` trusts any certificate; ``peer_fingerprint`` accepts only the
      certificate with that MD5, SHA-1 or SHA-256 digest, in hex.
    - ``source_ip`` — the local address sessions leave from; ``timeout`` — seconds to wait to
      connect and for each reply; ``local_domain`` — the name ``EHLO`` gives.
    - ``max_per_second`` — the most emails sent a second; ``restart_threshold`` — the emails
      after which the session is ended, ``restart_threshold_sleep`` the seconds waited then;
      ``ping_threshold`` — the idle seconds after which a ``NOOP`` precedes the next email.

    An option holding no valid value is refused by its name; the error quotes neither the DSN
    nor its credentials. The transport's HTTP client is not used: SMTP reaches the server itself.
    """

    @override
    def create(self, dsn: Dsn) -> EsmtpTransport:
        """Build the ESMTP transport ``dsn`` describes; nothing connects yet.

        Raises:
            UnsupportedSchemeError: ``dsn``'s scheme is neither ``smtp`` nor ``smtps``.
            InvalidArgumentError: An option holds no valid value, or the host or the port
                could not be connected to.
        """
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "smtp", self._get_supported_schemes())
        auto_tls = read_flag(dsn, "auto_tls")
        tls = True if dsn.scheme == "smtps" else (None if auto_tls else False)
        transport = EsmtpTransport(
            dsn.host,
            dsn.get_port() or 0,
            tls,
            event_dispatcher=self._event_dispatcher,
            logger=self._logger,
        )
        _ = transport.set_auto_tls(auto_tls).set_require_tls(dsn.get_boolean_option("require_tls"))
        _configure_connection(transport, dsn)
        if dsn.user:
            _ = transport.set_username(dsn.user)
        if dsn.password:
            _ = transport.set_password(dsn.password)
        _configure_session(transport, dsn)
        return transport

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        """Return ``smtp`` and ``smtps``."""
        return ("smtp", "smtps")


def _configure_connection(transport: EsmtpTransport, dsn: Dsn) -> None:
    """Set where ``transport`` connects from, how long it waits, and how it checks the server."""
    source_ip = read_text(dsn, "source_ip", _ADDRESS)
    if source_ip:
        if not is_ip_address(source_ip):
            raise refusal("source_ip", _ADDRESS, source_ip)
        _ = transport.set_source_ip(source_ip)
    timeout = read_number(dsn, "timeout", "a positive number of seconds", positive=True)
    if timeout is not None:
        _ = transport.set_timeout(timeout)
    if not read_flag(dsn, "verify_peer"):
        _ = transport.set_verify_peer(False)
    fingerprint = read_text(dsn, "peer_fingerprint", _DIGEST)
    if fingerprint is not None:
        if not is_digest(fingerprint):
            raise refusal("peer_fingerprint", _DIGEST, fingerprint)
        _ = transport.set_peer_fingerprint(fingerprint)


def _configure_session(transport: EsmtpTransport, dsn: Dsn) -> None:
    """Set the name ``transport`` greets with, its pace, and when it restarts or pings."""
    local_domain = read_text(dsn, "local_domain", _DOMAIN)
    if local_domain is not None:
        if any(character.isspace() for character in local_domain):
            # The name goes out in EHLO: one with a space in it would split the command.
            raise refusal("local_domain", _DOMAIN, local_domain)
        _ = transport.set_local_domain(local_domain)
    rate = read_number(dsn, "max_per_second", "a number of emails a second, zero or more")
    if rate is not None:
        _ = transport.set_max_per_second(rate)
    threshold = read_count(dsn, "restart_threshold", "a whole number of emails, zero or more")
    if threshold is not None:
        sleep = read_number(dsn, "restart_threshold_sleep", _SECONDS)
        _ = transport.set_restart_threshold(threshold, sleep or 0)
    ping = read_number(dsn, "ping_threshold", _SECONDS)
    if ping is not None:
        _ = transport.set_ping_threshold(ping)
