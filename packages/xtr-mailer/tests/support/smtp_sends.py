"""Transports pointed at a scripted SMTP server, and what they send it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_mime import Address, Email, RawMessage

from xtr_mailer import Envelope
from xtr_mailer.transport.smtp import EsmtpTransport, SmtpTransport

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_logging_contracts import LoggerInterface

    from tests.support.scripted_smtp_server import ScriptedSmtpServer

__all__ = ["email", "envelope", "esmtp_transport", "raw", "smtp_transport"]


def smtp_transport(
    server: ScriptedSmtpServer,
    *,
    clock: ClockInterface | None = None,
    logger: LoggerInterface | None = None,
    event_dispatcher: EventDispatcherInterface | None = None,
) -> SmtpTransport:
    """An SMTP transport speaking plain text to ``server``, waiting two seconds a reply."""
    return SmtpTransport(
        server.host,
        server.port,
        tls=False,
        event_dispatcher=event_dispatcher,
        logger=logger,
        clock=clock,
    ).set_timeout(2.0)


def esmtp_transport(
    server: ScriptedSmtpServer,
    *,
    host: str | None = None,
    logger: LoggerInterface | None = None,
) -> EsmtpTransport:
    """An ESMTP transport to ``server``, as ``host``, waiting two seconds a reply."""
    return EsmtpTransport(host or server.host, server.port, logger=logger).set_timeout(2.0)


def envelope() -> Envelope:
    """One sender, one recipient."""
    return Envelope(Address("sender@example.org"), [Address("recipient@example.org")])


def raw(text: str = "Message") -> RawMessage:
    """A raw message, sent as it is."""
    return RawMessage(text.encode())


def email() -> Email:
    """A text email from the envelope's sender to its recipient."""
    return Email().from_("sender@example.org").to("recipient@example.org").text(".")
