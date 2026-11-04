"""End-to-end: what the transports and the listeners log reaches the mailer's own channel."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_logging import Logger, TestHandler
from xtr_logging_contracts import Level, LoggerInterface
from xtr_mime import Email

from tests.support.mailer_kernel import Application, Provided, mailer_kernel
from tests.support.recording_transport_factory import RecordingTransportFactory
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smime_identities import identity
from xtr_mailer import MailerInterface
from xtr_mailer.bundle import MAILER_TRANSPORT_FACTORY_TAG, MailerConfig, SmimeEncrypterConfig

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_logging import LogRecord

pytestmark = pytest.mark.anyio

#: The channel an application's logging configuration routes the mailer's records by.
_CHANNEL = "mailer"


def _email() -> Email:
    return (
        Email()
        .from_("sender@example.com")
        .to("r1@example.com")
        .bcc("hidden@example.com")
        .subject("Hi")
        .text("Hello")
    )


async def _logged(application: Application, email: Email) -> tuple[LogRecord, ...]:
    """Send ``email`` in a kernel of ``application``; return what the mailer's channel took."""
    handler = TestHandler()
    async with await mailer_kernel(application).boot() as booted:
        logger = await booted.container.get(LoggerInterface, _CHANNEL)
        assert isinstance(logger, Logger)
        logger.push_handler(handler)
        await (await booted.container.get(MailerInterface)).send(email)
    return handler.records


async def test_a_recipient_without_a_certificate_is_logged_on_the_mailer_channel(
    tmp_path: Path,
) -> None:
    certificate, _ = identity("r1@example.com").write(tmp_path, "r1")
    encrypter = SmimeEncrypterConfig(
        certificates={"r1@example.com": str(certificate)}, on_missing_certificate="encrypt"
    )
    email = _email()
    _ = email.get_headers().add_text_header("X-SMime-Encrypt", "true")

    records = await _logged(Application(mailer=MailerConfig(smime_encrypter=encrypter)), email)

    [warning] = [record for record in records if record.level is Level.WARNING]
    assert (warning.channel, warning.message, dict(warning.context)) == (
        _CHANNEL,
        "Some recipients have no S/MIME certificate.",
        {"recipients": ["hidden@example.com"], "on_missing_certificate": "encrypt"},
    )


async def test_a_transport_found_by_its_scheme_logs_on_the_mailer_channel() -> None:
    async with ScriptedSmtpServer() as server:
        application = Application(mailer=MailerConfig(dsn=f"smtp://localhost:{server.port}"))
        records = await _logged(application, _email())

    assert (_CHANNEL, 'Email transport "{transport}" starting') in [
        (record.channel, record.message) for record in records
    ]


async def test_a_failing_member_of_a_group_is_logged_on_the_mailer_channel() -> None:
    factory = RecordingTransportFactory()
    application = Application(
        mailer=MailerConfig(dsn="failover(fake://down fake://backup)"),
        provided=[Provided(factory, tag=MAILER_TRANSPORT_FACTORY_TAG)],
    )

    records = await _logged(application, _email())

    [error] = [record for record in records if record.level is Level.ERROR]
    assert (error.channel, error.message, error.context["transport"]) == (
        _CHANNEL,
        'Transport "{transport}" failed.',
        "fake://down",
    )
