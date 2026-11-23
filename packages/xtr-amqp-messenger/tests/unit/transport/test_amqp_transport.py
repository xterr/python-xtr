"""What an ``amqp://`` transport offers beyond sending: its topology set up, its queue counted."""

# The broker keeps what it was built with in private attributes with no public
# accessor; a test reads them to see what setting up declared.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

import aio_pika
import pytest
from aio_pika.exceptions import ChannelInvalidStateError, ChannelNotFoundEntity
from taskiq_aio_pika import AioPikaBroker
from xtr_messenger import (
    FailureTransportWorkerProvidingInterface,
    MessageCountAwareInterface,
    SetupableTransportInterface,
    TransportConfig,
)

from tests.support.serialization import json_serializer
from xtr_amqp_messenger import AmqpTransport, AmqpTransportFactory, TransportError
from xtr_amqp_messenger.transport.delaying_broker import DelayingBroker

if TYPE_CHECKING:
    from types import TracebackType

pytestmark = pytest.mark.anyio

_HOST = "amqp://guest:s3cr%40t@localhost:5672/"


def _transport(query: str = "queue=jobs&auto_setup=false") -> AmqpTransport:
    group = {
        "jobs": TransportConfig(f"{_HOST}?{query}"),
        "mail": TransportConfig(f"{_HOST}?queue=mail&auto_setup=false"),
    }
    built = AmqpTransportFactory(json_serializer()).create(group)["jobs"]
    assert isinstance(built, AmqpTransport)
    return built


def test_it_can_be_set_up_and_counted() -> None:
    transport = _transport()

    assert isinstance(transport, SetupableTransportInterface)
    assert isinstance(transport, MessageCountAwareInterface)


def test_it_reads_what_its_sender_was_built_with() -> None:
    transport = _transport()

    assert isinstance(transport.broker, DelayingBroker)
    assert transport.broker is transport.sender.broker
    assert transport.queue == "jobs"
    assert transport.serializer is transport.sender.serializer


def test_its_factory_sends_final_failures_to_a_failure_transport() -> None:
    assert isinstance(
        AmqpTransportFactory(json_serializer()), FailureTransportWorkerProvidingInterface
    )


async def test_setting_up_declares_everything_whatever_auto_setup_says(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[AioPikaBroker] = []
    stopped: list[AioPikaBroker] = []

    async def startup(self: AioPikaBroker) -> None:
        started.append(self)

    async def shutdown(self: AioPikaBroker) -> None:
        stopped.append(self)

    monkeypatch.setattr(AioPikaBroker, "startup", startup)
    monkeypatch.setattr(AioPikaBroker, "shutdown", shutdown)

    await _transport().setup()

    [broker] = started
    assert stopped == [broker]
    assert broker._exchange.declare
    assert broker._dead_letter_queue.declare
    assert [(queue.name, queue.declare) for queue in broker._task_queues] == [
        ("jobs", True),
        ("mail", True),
    ]


async def test_a_refused_setup_is_a_transport_error_without_the_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def refuse(self: AioPikaBroker) -> None:
        del self
        raise ConnectionRefusedError("refused amqp://guest:s3cr@t@localhost and s3cr%40t")

    async def fail_to_close(self: AioPikaBroker) -> None:
        del self
        raise ConnectionResetError("reset while closing")

    monkeypatch.setattr(AioPikaBroker, "startup", refuse)
    monkeypatch.setattr(AioPikaBroker, "shutdown", fail_to_close)

    with pytest.raises(TransportError) as raised:
        await _transport().setup()

    assert raised.value.operation == "set up"
    assert "refused" in raised.value.reason
    assert "s3cr" not in str(raised.value)


async def test_a_setup_that_cannot_close_is_a_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def startup(self: AioPikaBroker) -> None:
        del self

    async def fail_to_close(self: AioPikaBroker) -> None:
        del self
        raise ConnectionResetError("reset while closing")

    monkeypatch.setattr(AioPikaBroker, "startup", startup)
    monkeypatch.setattr(AioPikaBroker, "shutdown", fail_to_close)

    with pytest.raises(TransportError) as raised:
        await _transport().setup()

    assert raised.value.operation == "close after setting up"


@dataclass
class _Declared:
    message_count: int | None


@dataclass
class _Queue:
    declaration_result: _Declared


@dataclass
class _Channel:
    counts: dict[str, int]

    async def declare_queue(self, name: str, *, passive: bool) -> _Queue:
        assert passive
        if name == "closed":
            raise ChannelInvalidStateError("channel closed")
        if name not in self.counts:
            raise ChannelNotFoundEntity(f"no queue '{name}'")
        return _Queue(_Declared(self.counts[name]))


@dataclass
class _Connection:
    counts: dict[str, int]
    closed: bool = False

    async def channel(self) -> _Channel:
        return _Channel(self.counts)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.closed = True


def _broker_holding(monkeypatch: pytest.MonkeyPatch, **counts: int) -> list[_Connection]:
    opened: list[_Connection] = []

    # The driver's own signature, timeout included, which the fake stands in for.
    async def connect(url: str, **options: object) -> _Connection:
        del url, options
        opened.append(_Connection(counts))
        return opened[-1]

    monkeypatch.setattr(aio_pika, "connect", connect)
    return opened


async def test_counting_reads_the_transports_own_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    opened = _broker_holding(monkeypatch, jobs=7, mail=2)

    assert await _transport().count() == 7
    assert [connection.closed for connection in opened] == [True]


async def test_a_transport_naming_no_queue_counts_the_default_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = {"jobs": TransportConfig(_HOST)}
    built = AmqpTransportFactory(json_serializer()).create(group)["jobs"]
    assert isinstance(built, AmqpTransport)
    _ = _broker_holding(monkeypatch, taskiq=3)

    assert await built.count() == 3


async def test_counting_a_missing_queue_is_a_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = _broker_holding(monkeypatch)

    with pytest.raises(TransportError) as raised:
        _ = await _transport().count()

    assert raised.value.transport == "jobs"
    assert raised.value.operation == "count messages"


async def test_counting_on_a_closed_channel_is_a_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = _broker_holding(monkeypatch)

    with pytest.raises(TransportError):
        _ = await _transport("queue=closed").count()
