"""How a delayed message is held back: settled from the server's version, then sent."""

# The broker keeps its channel and connection in attributes the library sets
# at startup; a test stands fakes in for them.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import pytest
from aio_pika import Message
from taskiq import BrokerMessage
from taskiq_aio_pika import AioPikaBroker
from taskiq_aio_pika.exceptions import NoStartupError
from xtr_clock import MockClock
from xtr_messenger import InvalidTransportOptionError

from xtr_amqp_messenger.transport.amqp_broker import create_amqp_broker
from xtr_amqp_messenger.transport.amqp_options import AmqpOptions
from xtr_amqp_messenger.transport.delaying_broker import DELIVERY_TIME_HEADER, DelayingBroker
from xtr_amqp_messenger.transport.queue_options import QueueOptions

if TYPE_CHECKING:
    from aio_pika.abc import AbstractChannel, AbstractRobustConnection

pytestmark = pytest.mark.anyio

_HOST = "amqp://guest:guest@localhost:5672/"
_NOW = "2026-01-01T00:00:00+00:00"
_NOW_MS = 1_767_225_600_000


@dataclass
class _Exchange:
    published: list[tuple[Message, str]] = field(default_factory=list)

    async def publish(self, message: Message, routing_key: str) -> None:
        self.published.append((message, routing_key))


@dataclass
class _Channel:
    exchange: _Exchange = field(default_factory=_Exchange)
    default_exchange: _Exchange = field(default_factory=_Exchange)
    declared: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    async def get_exchange(self, name: str, *, ensure: bool = True) -> _Exchange:
        del name, ensure
        return self.exchange

    async def declare_queue(
        self, name: str, *, durable: bool, arguments: dict[str, object]
    ) -> None:
        assert durable
        self.declared.append((name, arguments))


@dataclass
class _Connection:
    """What the version is read off: the server properties the server sent."""

    version: str

    @property
    def transport(self) -> _Connection:
        return self

    @property
    def connection(self) -> _Connection:
        return self

    @property
    def server_properties(self) -> dict[str, object]:
        return {"version": self.version}


def _broker(
    options: AmqpOptions | None = None, queues: tuple[str, ...] = ("jobs",)
) -> DelayingBroker:
    broker = create_amqp_broker(_HOST, options, queues, clock=MockClock(_NOW))
    assert isinstance(broker, DelayingBroker)
    return broker


def _started(broker: DelayingBroker) -> _Channel:
    channel = _Channel()
    # Only what the broker calls is faked, which no type checker can see.
    broker.write_channel = cast("AbstractChannel", cast("object", channel))
    return channel


def _message(**labels: object) -> BrokerMessage:
    return BrokerMessage(task_id="t-1", task_name="job", message=b"{}", labels=dict(labels))


async def _connected(broker: DelayingBroker, version: str, monkeypatch: pytest.MonkeyPatch) -> None:
    async def connect(self: AioPikaBroker) -> None:
        # Only the server properties are read off the connection.
        self.write_conn = cast("AbstractRobustConnection", cast("object", _Connection(version)))

    monkeypatch.setattr(AioPikaBroker, "startup", connect)
    await broker.startup()


@pytest.mark.parametrize(("version", "delay"), [("4.4.1", "native"), ("4.2.4", "queue")])
async def test_auto_delays_natively_from_rabbitmq_4_4_on(
    version: str, delay: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = _broker()

    await _connected(broker, version, monkeypatch)

    assert broker.delay == delay


async def test_auto_delays_in_queues_when_the_queues_cannot_hold_a_message_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = _broker(AmqpOptions(queue=QueueOptions(type="classic")))

    await _connected(broker, "4.4.1", monkeypatch)

    assert broker.delay == "queue"


async def test_an_unreadable_version_delays_in_queues(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = _broker()

    await _connected(broker, "unknown", monkeypatch)

    assert broker.delay == "queue"


async def test_a_chosen_delay_is_kept_once_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = _broker(AmqpOptions(delay="queue"))

    await _connected(broker, "4.4.1", monkeypatch)

    assert broker.delay == "queue"


async def test_a_native_delay_is_refused_by_a_server_that_would_ignore_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = _broker(AmqpOptions(delay="native"))
    shut: list[bool] = []

    async def shutdown(self: AioPikaBroker) -> None:
        del self
        shut.append(True)

    monkeypatch.setattr(AioPikaBroker, "shutdown", shutdown)

    with pytest.raises(InvalidTransportOptionError, match=r"the server is 4\.2"):
        await _connected(broker, "4.2.4", monkeypatch)
    assert shut == [True]


async def test_a_native_delay_is_kept_by_a_server_that_honours_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = _broker(AmqpOptions(delay="native"))

    await _connected(broker, "4.4.1", monkeypatch)

    assert broker.delay == "native"


async def test_a_native_delay_is_sent_as_the_time_it_ends_at() -> None:
    broker = _broker(AmqpOptions(delay="native"))
    channel = _started(broker)

    await broker.kick(_message(delay="2.5"))

    [(message, routing_key)] = channel.exchange.published
    assert routing_key == "jobs"
    assert message.headers[DELIVERY_TIME_HEADER] == _NOW_MS + 2500
    assert message.headers["task_name"] == "job"
    assert not channel.declared


async def test_a_queued_delay_waits_in_a_queue_dead_lettering_back_to_its_own() -> None:
    broker = _broker(AmqpOptions(delay="queue"))
    channel = _started(broker)

    await broker.kick(_message(delay="2"))

    [(queue, arguments)] = channel.declared
    assert queue == "taskiq.delay.jobs.2000"
    assert arguments == {
        "x-message-ttl": 2000,
        "x-dead-letter-exchange": "taskiq",
        "x-dead-letter-routing-key": "jobs",
        "x-expires": 12000,
    }
    [(message, routing_key)] = channel.default_exchange.published
    assert routing_key == queue
    assert DELIVERY_TIME_HEADER not in message.headers


async def test_a_delayed_message_is_routed_to_the_queue_it_names() -> None:
    broker = _broker(AmqpOptions(delay="queue"), queues=("high", "low"))
    channel = _started(broker)

    await broker.kick(_message(delay="1", queue_name="low"))

    [(queue, arguments)] = channel.declared
    assert queue == "taskiq.delay.low.1000"
    assert arguments["x-dead-letter-routing-key"] == "low"


async def test_a_message_sent_without_a_delay_is_published_as_usual() -> None:
    broker = _broker(AmqpOptions(delay="native"))
    channel = _started(broker)

    await broker.kick(_message())

    [(message, _)] = channel.exchange.published
    assert DELIVERY_TIME_HEADER not in message.headers
    assert not channel.declared


async def test_a_delayed_message_needs_the_broker_started() -> None:
    with pytest.raises(NoStartupError):
        await _broker(AmqpOptions(delay="queue")).kick(_message(delay="1"))
