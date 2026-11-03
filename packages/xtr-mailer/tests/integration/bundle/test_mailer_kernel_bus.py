"""End-to-end: an application routing queued email to a broker, sent by a worker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest
import xtr_messenger.message_registry
from xtr_http_client.bundle import HttpClientConfig
from xtr_messenger import MessageBusConfig, TransportConfig, WorkerFactory, name_of
from xtr_mime import Email

from tests.support.mailer_kernel import Application, Provided, mailer_kernel
from tests.support.recording_transport_factory import RecordingTransportFactory
from xtr_mailer import MailerInterface
from xtr_mailer.bundle import MAILER_TRANSPORT_FACTORY_TAG, MailerConfig
from xtr_mailer.event_listener import MessageLoggerListener
from xtr_mailer.messenger import SendEmailMessage

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

pytestmark = pytest.mark.anyio


class _Unchecked(Protocol):
    """A protocol no class can be checked against."""

    def written(self) -> object: ...


def _queuing(
    factory: RecordingTransportFactory,
    routing: Mapping[type | str, str | Sequence[str]] | None = None,
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


@pytest.mark.parametrize(
    ("routing", "queued"),
    [
        ({SendEmailMessage: "mail"}, True),
        ({object: ["mail"]}, True),
        ({"*": "mail"}, True),
        ({name_of(SendEmailMessage): "mail"}, False),
        ({_Unchecked: "mail"}, False),
        ({SendEmailMessage: []}, False),
        ({}, False),
    ],
    ids=["class", "base class", "catch-all", "wire name", "protocol", "no transport", "none"],
)
async def test_an_email_is_queued_for_the_worker_or_sent_at_once_never_dropped(
    routing: Mapping[type | str, str | Sequence[str]], queued: bool
) -> None:
    factory = RecordingTransportFactory()

    async with await mailer_kernel(_queuing(factory, routing)).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(_email())
        sent_at_once = len(factory.sent)
        await (await booted.container.get(WorkerFactory)).worker(["mail"]).run()

    assert (sent_at_once, len(factory.sent)) == ((0, 1) if queued else (1, 1))


async def test_an_email_whose_class_declares_its_transport_is_queued_for_the_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declared = xtr_messenger.message_registry._TRANSPORTS_BY_TYPE
    monkeypatch.setitem(declared, SendEmailMessage, ("mail",))
    factory = RecordingTransportFactory()

    async with await mailer_kernel(_queuing(factory, routing={})).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(_email())
        sent_before = list(factory.sent)
        await (await booted.container.get(WorkerFactory)).worker(["mail"]).run()

    assert sent_before == []
    assert [name for name, _ in factory.sent] == ["main"]
