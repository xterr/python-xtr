"""End-to-end: an application routing queued email to a broker, sent by a worker."""

from __future__ import annotations

import pytest
from xtr_http_client.bundle import HttpClientConfig
from xtr_messenger import MessageBusConfig, TransportConfig, WorkerFactory
from xtr_mime import Email

from tests.support.mailer_kernel import Application, Provided, mailer_kernel
from tests.support.recording_transport_factory import RecordingTransportFactory
from xtr_mailer import MailerInterface
from xtr_mailer.bundle import MAILER_TRANSPORT_FACTORY_TAG, MailerConfig
from xtr_mailer.event_listener import MessageLoggerListener
from xtr_mailer.messenger import SendEmailMessage

pytestmark = pytest.mark.anyio


def _queuing(
    factory: RecordingTransportFactory, routing: dict[type | str, str] | None = None
) -> Application:
    bus = MessageBusConfig(
        transports={
            "mail": TransportConfig("in-memory://?serialize=true"),
            "bulk": TransportConfig("in-memory://?serialize=true"),
        },
        routing=routing if routing is not None else {SendEmailMessage: "mail"},
    )
    return Application(
        mailer=MailerConfig(dsn="fake://main"),
        # A test never reaches the network: the client the transports are handed answers itself.
        peers={"messenger": bus, "http_client": HttpClientConfig(mock_response_factory=True)},
        provided=[Provided(factory, tag=MAILER_TRANSPORT_FACTORY_TAG)],
    )


def _email() -> Email:
    return Email().from_("shop@example.com").to("customer@example.com").subject("Hi").text("Hello")


async def test_a_routed_email_is_queued_and_sent_by_the_worker() -> None:
    factory = RecordingTransportFactory()

    async with await mailer_kernel(_queuing(factory)).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(_email())
        logger = await booted.container.get(MessageLoggerListener)
        queued = [event.is_queued() for event in logger.get_events().get_events()]
        sent_before = list(factory.sent)
        await (await booted.container.get(WorkerFactory)).worker(["mail"]).run()

    assert queued == [True]
    assert sent_before == []
    [(name, sent)] = factory.sent
    assert name == "main"
    message = sent.get_original_message()
    assert isinstance(message, Email)
    assert message.get_subject() == "Hi"


async def test_the_bus_transport_header_picks_the_queue() -> None:
    factory = RecordingTransportFactory()
    email = _email()
    _ = email.get_headers().add_text_header("X-Bus-Transport", "bulk")

    async with await mailer_kernel(_queuing(factory)).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(email)
        workers = await booted.container.get(WorkerFactory)
        await workers.worker(["mail"]).run()
        sent_from_mail = list(factory.sent)
        await workers.worker(["bulk"]).run()

    assert sent_from_mail == []
    assert [name for name, _ in factory.sent] == ["main"]


async def test_an_email_the_bus_does_not_route_is_sent_at_once() -> None:
    factory = RecordingTransportFactory()

    async with await mailer_kernel(_queuing(factory, routing={})).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(_email())

    assert [name for name, _ in factory.sent] == ["main"]
