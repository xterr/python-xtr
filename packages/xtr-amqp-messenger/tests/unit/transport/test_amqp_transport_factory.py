"""Building RabbitMQ transports, and scoping a worker to some of them.

A producer needs one broker knowing every queue it publishes to; a worker
needs a broker consuming only its own. Both come from the same factory, using
real ``AioPikaBroker`` objects — construction opens no connection.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, final

import pytest
from taskiq import Context, SmartRetryMiddleware, TaskiqMessage
from taskiq_aio_pika import AioPikaBroker
from xtr_messenger import (
    Dsn,
    Envelope,
    FailureTransportSender,
    InMemoryTransport,
    InMemoryTransportFactory,
    MessageBusConfig,
    MixedDsnError,
    PublisherClosingInterface,
    SentToFailureTransportStamp,
    TransportConfig,
    TransportLocator,
    UnknownTransportOptionError,
    WorkerInterface,
    WorkerProvidingInterface,
    name_of,
)
from xtr_messenger.bridge.taskiq.labels import HEADERS_LABEL, RETRIES_LABEL
from xtr_messenger.bridge.taskiq.taskiq_worker import TaskiqWorker, default_max_async_tasks
from xtr_messenger.message_registry import declared_names

from tests.support.fakes import RecordingBus
from tests.support.messages import IngestDocument, ingest_document
from tests.support.serialization import json_serializer
from xtr_amqp_messenger.transport import AmqpTransportFactory, declared_queues
from xtr_amqp_messenger.transport.amqp_transport import AmqpTransport

if TYPE_CHECKING:
    from xtr_messenger.bridge.taskiq.taskiq_sender import TaskiqSender

_HOST = "amqp://guest:guest@localhost:5672/"
_OTHER = "amqp://guest:guest@other:5672/"


@final
class CountingResetter:
    """Counts the resets the worker owes after each message."""

    def __init__(self) -> None:
        self.resets: int = 0

    async def reset(self) -> None:
        self.resets += 1


def _group() -> dict[str, TransportConfig]:
    return {
        "high": TransportConfig(_HOST, queue="jobs_high"),
        "low": TransportConfig(_HOST, queue="jobs_low"),
    }


def _sender(built: object) -> TaskiqSender:
    assert isinstance(built, AmqpTransport)
    return built.sender


def _broker_of(sender: object) -> AioPikaBroker:
    broker = _sender(sender).broker
    assert isinstance(broker, AioPikaBroker)
    return broker


def _worker_broker(worker: object) -> AioPikaBroker:
    assert isinstance(worker, TaskiqWorker)
    broker = worker.broker
    assert isinstance(broker, AioPikaBroker)
    return broker


def test_construction_opens_no_connection() -> None:
    senders = AmqpTransportFactory(json_serializer()).create(_group())

    assert _broker_of(senders["high"]).write_channel is None


def test_the_producer_broker_declares_every_queue_it_publishes_to() -> None:
    senders = AmqpTransportFactory(json_serializer()).create(_group())

    assert declared_queues(_broker_of(senders["high"])) == ("jobs_high", "jobs_low")


def test_a_sender_carries_the_queue_its_transport_named() -> None:
    sender = _sender(AmqpTransportFactory(json_serializer()).create(_group())["low"])

    assert sender.queue == "jobs_low"


def test_transports_sharing_a_connection_share_one_broker() -> None:
    senders = AmqpTransportFactory(json_serializer()).create(_group())

    assert _broker_of(senders["high"]) is _broker_of(senders["low"])


def test_a_queue_in_the_dsn_still_groups_onto_one_broker() -> None:
    group = {
        "high": TransportConfig(_HOST, queue="jobs_high"),
        "low": TransportConfig(f"{_HOST}?queue=jobs_low"),
    }

    senders = AmqpTransportFactory(json_serializer()).create(group)

    assert _broker_of(senders["high"]) is _broker_of(senders["low"])


def test_a_worker_declares_only_the_queues_it_was_given() -> None:
    worker = AmqpTransportFactory(json_serializer()).worker(
        {"high": _group()["high"]}, RecordingBus()
    )

    assert declared_queues(_worker_broker(worker)) == ("jobs_high",)


def test_a_worker_can_serve_several_queues_at_once() -> None:
    worker = AmqpTransportFactory(json_serializer()).worker(_group(), RecordingBus())

    assert declared_queues(_worker_broker(worker)) == ("jobs_high", "jobs_low")


def test_a_worker_spanning_two_connections_fails_loudly() -> None:
    group = {
        "here": TransportConfig(_HOST, queue="jobs"),
        "there": TransportConfig(_OTHER, queue="jobs"),
    }

    with pytest.raises(MixedDsnError) as excinfo:
        _ = AmqpTransportFactory(json_serializer()).worker(group, RecordingBus())

    assert len(excinfo.value.dsns) == 2


def test_the_worker_binds_a_task_for_every_declared_message() -> None:
    """The consumer half registers a task per declared name, dispatching into
    the bus it was given — so ``run`` needs no further wiring."""
    worker = AmqpTransportFactory(json_serializer()).worker(
        {"high": _group()["high"]}, RecordingBus()
    )

    tasks = _worker_broker(worker).get_all_tasks()
    assert all(name in tasks for name in declared_names())
    assert name_of(IngestDocument) in tasks


def test_the_worker_is_a_taskiq_worker() -> None:
    worker = AmqpTransportFactory(json_serializer()).worker(
        {"high": _group()["high"]}, RecordingBus()
    )

    assert isinstance(worker, WorkerInterface)
    assert isinstance(worker, TaskiqWorker)


def test_the_worker_handles_the_configured_number_of_messages_at_once() -> None:
    group = {"high": TransportConfig(f"{_HOST}?queue=jobs_high&max_async_tasks=7")}

    worker = AmqpTransportFactory(json_serializer()).worker(group, RecordingBus())

    assert isinstance(worker, TaskiqWorker)
    assert worker.max_async_tasks == 7


def test_the_worker_is_bounded_by_default() -> None:
    worker = AmqpTransportFactory(json_serializer()).worker(
        {"high": _group()["high"]}, RecordingBus()
    )

    assert isinstance(worker, TaskiqWorker)
    assert worker.max_async_tasks == default_max_async_tasks()


def test_both_halves_share_one_serializer() -> None:
    """Producer and consumer are separate deploys; what one factory builds for
    either half writes and reads with the one serializer it was given."""
    mine = json_serializer()
    factory = AmqpTransportFactory(mine)

    sender = _sender(factory.create({"q": TransportConfig(_HOST, queue="jobs")})["q"])

    assert sender.serializer is mine


def test_it_is_a_worker_providing_interface() -> None:
    assert isinstance(AmqpTransportFactory(json_serializer()), WorkerProvidingInterface)


def test_it_is_a_publisher_closing_interface() -> None:
    """How a composite factory — and so the bundle's shutdown — finds the
    connections this adapter's senders opened."""
    assert isinstance(AmqpTransportFactory(json_serializer()), PublisherClosingInterface)


@pytest.mark.anyio
async def test_closing_publishers_after_no_publish_opens_nothing() -> None:
    """Nothing is recorded until a sender publishes, so a shutdown after no
    publish has nothing to release — and must not connect to find that out."""
    factory = AmqpTransportFactory(json_serializer())
    senders = factory.create(_group())

    await factory.close_publishers()

    assert _broker_of(senders["high"]).write_channel is None


def test_it_supports_the_amqp_schemes() -> None:
    factory = AmqpTransportFactory(json_serializer())

    assert factory.supports(Dsn.parse("amqp://host/"))
    assert factory.supports(Dsn.parse("amqps://host/"))
    assert not factory.supports(Dsn.parse("sync://"))


def test_options_override_the_dsn() -> None:
    """A DSN lives in an environment variable; options let code override it."""
    group = {
        "q": TransportConfig(f"{_HOST}?queue=jobs&max_attempts=3", options={"max_attempts": "9"})
    }

    broker = _broker_of(AmqpTransportFactory(json_serializer()).create(group)["q"])

    retry = next(m for m in broker.middlewares if isinstance(m, SmartRetryMiddleware))
    assert retry.default_retry_count == 9


def test_a_misspelled_option_is_refused() -> None:
    """The whole bug: an unread setting leaves the transport on defaults
    nobody chose."""
    group = {"q": TransportConfig(f"{_HOST}?queue=jobs&max_attempt=10")}

    with pytest.raises(UnknownTransportOptionError, match="max_attempt"):
        _ = AmqpTransportFactory(json_serializer()).create(group)


def test_an_option_meant_for_another_scheme_is_refused() -> None:
    group = {"q": TransportConfig(f"{_HOST}?queue=jobs&serialize=true")}

    with pytest.raises(UnknownTransportOptionError, match="serialize"):
        _ = AmqpTransportFactory(json_serializer()).create(group)


def test_disabling_verification_warns_once_per_factory(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A security downgrade must not be silent — but one warning per factory
    is a notice, while one per broker built is noise that buries it."""
    tls_host = "amqps://guest:guest@localhost:5671/"
    group = {"q": TransportConfig(f"{tls_host}?queue=jobs&verify=false")}
    factory = AmqpTransportFactory(json_serializer())

    with caplog.at_level(logging.WARNING, logger="messenger"):
        _ = factory.create(group)
        _ = factory.worker(group, RecordingBus())

    warned = [r for r in caplog.records if "verification is disabled" in r.message]
    assert len(warned) == 1


def test_a_verified_connection_never_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="messenger"):
        _ = AmqpTransportFactory(json_serializer()).create(_group())

    assert caplog.records == []


def test_the_workers_broker_is_not_recorded_as_a_publisher() -> None:
    """A worker's run loop closes its own broker; registering it with the
    publish-side bookkeeping was a no-op kept alive by habit."""
    worker = AmqpTransportFactory(json_serializer()).worker(
        {"high": _group()["high"]}, RecordingBus()
    )

    assert isinstance(worker, TaskiqWorker)
    assert worker._publishers is None  # pyright: ignore[reportPrivateUsage] -- no public accessor; the absence of the record is the behaviour


@pytest.mark.anyio
async def test_the_worker_resets_services_after_each_message() -> None:
    """The resetter must reach the taskiq binding: the library's own worker
    resets after each message, and the AMQP worker owes the same contract."""
    resetter = CountingResetter()
    bus = RecordingBus()
    worker = AmqpTransportFactory(json_serializer()).worker(
        {"high": _group()["high"]}, bus, resetter=resetter
    )
    broker = _worker_broker(worker)
    task = broker.find_task(name_of(IngestDocument))
    assert task is not None
    encoded = json_serializer().encode(Envelope.wrap(ingest_document()))
    message = TaskiqMessage(
        task_id="t1",
        task_name=name_of(IngestDocument),
        labels={RETRIES_LABEL: 0, HEADERS_LABEL: json.dumps(encoded.headers)},
        args=[],
        kwargs={},
    )

    await task.original_func(encoded.body, Context(message, broker))

    assert resetter.resets == 1
    assert len(bus.dispatched) == 1


async def _fail_last_attempt(failure: str | None) -> tuple[bool, tuple[Envelope, ...]]:
    """Fail a message's last attempt on ``high``; tell whether it raised, and what moved."""
    config = MessageBusConfig(
        transports={"high": _group()["high"], "failed": TransportConfig("in-memory://")},
        failure_transport="failed",
    )
    locator = TransportLocator(config, [InMemoryTransportFactory()])
    factory = AmqpTransportFactory(json_serializer())
    bus = RecordingBus(failure=RuntimeError("boom"))
    group = {"high": config.transports["high"]}
    worker = (
        factory.worker(group, bus)
        if failure is None
        else factory.worker_with_failure_transport(
            group, bus, FailureTransportSender(config, locator)
        )
    )
    broker = _worker_broker(worker)
    task = broker.find_task(name_of(IngestDocument))
    assert task is not None
    encoded = json_serializer().encode(Envelope.wrap(ingest_document()))
    message = TaskiqMessage(
        task_id="t1",
        task_name=name_of(IngestDocument),
        labels={RETRIES_LABEL: 2, HEADERS_LABEL: json.dumps(encoded.headers)},
        args=[],
        kwargs={},
    )
    raised = False
    try:
        await task.original_func(encoded.body, Context(message, broker))
    except RuntimeError:
        raised = True
    failed = locator.get("failed")
    assert isinstance(failed, InMemoryTransport)
    return raised, failed.sent


@pytest.mark.anyio
async def test_a_worker_with_a_failure_transport_sends_a_last_attempt_there() -> None:
    raised, moved = await _fail_last_attempt("failed")

    assert not raised
    [envelope] = moved
    stamp = envelope.last(SentToFailureTransportStamp)
    assert stamp is not None
    assert stamp.original_receiver_name == "high"


@pytest.mark.anyio
async def test_a_plain_worker_leaves_a_last_attempt_to_dead_lettering() -> None:
    raised, moved = await _fail_last_attempt(None)

    assert raised
    assert moved == ()


def test_with_the_delay_plugin_off_senders_still_accept_a_delay() -> None:
    """Without the plugin a delay is held back natively or in a delay queue."""
    group = {"q": TransportConfig(f"{_HOST}?queue=jobs&delayed_message_exchange_plugin=false")}

    sender = _sender(AmqpTransportFactory(json_serializer()).create(group)["q"])

    assert sender._supports_delay is True  # pyright: ignore[reportPrivateUsage] -- no public accessor


def test_by_default_senders_accept_a_delay() -> None:
    sender = _sender(AmqpTransportFactory(json_serializer()).create(_group())["high"])

    assert sender._supports_delay is True  # pyright: ignore[reportPrivateUsage] -- no public accessor
