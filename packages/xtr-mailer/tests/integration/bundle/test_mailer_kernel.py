"""End-to-end: an application listing the mailer bundle sends through the transports it names."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import Application as ConsoleApplication
from xtr_console import ApplicationTester, ExitCode
from xtr_dependency_injection import env
from xtr_mime import Address, Email, Message

from tests.support.mailer_kernel import Application, Provided, mailer_kernel
from tests.support.recording_transport_factory import RecordingTransportFactory
from xtr_mailer import Mailer, MailerInterface
from xtr_mailer.bundle import (
    MAILER_TRANSPORT_FACTORY_TAG,
    EnvelopeConfig,
    MailerConfig,
    TrackingConfig,
)
from xtr_mailer.event_listener import MessageLoggerListener
from xtr_mailer.header import TrackingHeader
from xtr_mailer.transport import TransportInterface, Transports

if TYPE_CHECKING:
    from xtr_mime.header import Headers

pytestmark = pytest.mark.anyio


def _email() -> Email:
    return Email().from_("shop@example.com").to("customer@example.com").subject("Hi").text("Hello")


def _recording(mailer: MailerConfig) -> tuple[Application, RecordingTransportFactory]:
    factory = RecordingTransportFactory()
    provided = Provided(factory, tag=MAILER_TRANSPORT_FACTORY_TAG)
    return Application(mailer=mailer, provided=[provided]), factory


async def test_the_dsn_read_from_the_environment_sends_in_process() -> None:
    application = Application(
        mailer=MailerConfig(dsn=env("MAILER_DSN")), environ={"MAILER_DSN": "null://null"}
    )

    async with await mailer_kernel(application).boot() as booted:
        mailer = await booted.container.get(MailerInterface)
        await mailer.send(_email())
        logger = await booted.container.get(MessageLoggerListener)

    assert isinstance(mailer, Mailer)
    [event] = logger.get_events().get_events()
    assert (event.get_transport(), event.is_queued()) == ("null://", False)


async def test_a_failover_dsn_moves_to_the_next_transport() -> None:
    application, factory = _recording(
        MailerConfig(transports={"main": "failover(fake://down fake://backup)"})
    )

    async with await mailer_kernel(application).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(_email())

    assert [name for name, _ in factory.sent] == ["backup"]


async def test_an_email_naming_a_transport_goes_through_that_one() -> None:
    application, factory = _recording(
        MailerConfig(transports={"main": "fake://main", "marketing": "fake://marketing"})
    )
    email = _email()
    _ = email.get_headers().add_text_header("X-Transport", "marketing")

    async with await mailer_kernel(application).boot() as booted:
        transport = await booted.container.get(TransportInterface)
        await (await booted.container.get(MailerInterface)).send(email)
        await (await booted.container.get(MailerInterface)).send(_email())

    assert isinstance(transport, Transports)
    assert str(transport) == "[main,marketing]"
    assert [name for name, _ in factory.sent] == ["marketing", "main"]


async def test_the_envelope_headers_and_tracking_configured_reach_every_email() -> None:
    application = Application(
        mailer=MailerConfig(
            envelope=EnvelopeConfig(
                sender="bounces@example.com",
                recipients=["qa@example.com"],
                allowed_recipients=[r".*@example\.com"],
            ),
            headers={"X-App": "shop", "Bcc": ["audit@example.com"]},
            tracking=TrackingConfig(opens=False),
        )
    )
    email = _email().add_to("outsider@example.org")

    async with await mailer_kernel(application).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(email)
        logger = await booted.container.get(MessageLoggerListener)

    [event] = logger.get_events().get_events()
    envelope, headers = event.get_envelope(), _headers(event.get_message())
    assert envelope.get_sender() == Address("bounces@example.com")
    assert envelope.get_recipients() == [
        Address("qa@example.com"),
        Address("customer@example.com"),
        Address("audit@example.com"),
    ]
    assert headers.get_header_body("X-App") == "shop"
    assert headers.get_header_body("Bcc") == [Address("audit@example.com")]
    tracking = TrackingHeader.from_headers(headers)
    assert tracking is not None
    assert (tracking.get_opens(), tracking.get_clicks()) == (False, None)


async def test_a_tracking_header_configured_wins_over_the_tracking_option() -> None:
    application = Application(
        mailer=MailerConfig(
            headers={"X-Track": "opens=true; clicks=true"}, tracking=TrackingConfig(opens=False)
        )
    )

    async with await mailer_kernel(application).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(_email())
        logger = await booted.container.get(MessageLoggerListener)

    [event] = logger.get_events().get_events()
    tracking = TrackingHeader.from_headers(_headers(event.get_message()))
    assert tracking is not None
    assert (tracking.get_opens(), tracking.get_clicks()) == (True, True)


async def test_the_test_command_sends_through_the_transport_it_names() -> None:
    application, factory = _recording(
        MailerConfig(transports={"main": "fake://main", "backup": "fake://backup"})
    )

    async with await mailer_kernel(application).boot() as booted:
        tester = ApplicationTester(await booted.container.get(ConsoleApplication))
        code = await tester.execute(["mailer:test", "qa@example.com", "--transport", "backup"])

    assert code == ExitCode.SUCCESS
    [(name, sent)] = factory.sent
    assert name == "backup"
    assert sent.get_envelope().get_recipients() == [Address("qa@example.com")]


async def test_outside_debug_no_email_is_recorded() -> None:
    async with await mailer_kernel(Application(debug=False)).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(_email())

        assert not booted.container.has(MessageLoggerListener)


def _headers(message: object) -> Headers:
    assert isinstance(message, Message)
    return message.get_headers()
