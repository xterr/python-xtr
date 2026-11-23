"""The send half of an ``amqp://`` transport, and what can be asked of its queue."""

from __future__ import annotations

import contextlib
from dataclasses import replace
from typing import TYPE_CHECKING, Final, cast, final, override
from urllib.parse import unquote, urlsplit

import aio_pika
from aio_pika.exceptions import AMQPError, ChannelInvalidStateError
from taskiq_aio_pika.exceptions import BaseAioPikaBrokerError
from taskiq_aio_pika.queue import Queue
from xtr_messenger import MessageCountAwareInterface, SenderInterface, SetupableTransportInterface

from xtr_amqp_messenger.exception import TransportError

from .amqp_broker import create_amqp_broker

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_messenger import Envelope
    from xtr_messenger.bridge.taskiq.taskiq_sender import TaskiqSender
    from xtr_messenger.transport.serialization import SerializerInterface

    from .amqp_options import AmqpOptions
    from .delaying_broker import DelayingBroker

__all__ = ["AmqpTransport"]

#: What the driver raises for a broker that refused or could not be reached.
_BROKER_ERRORS: Final = (AMQPError, ChannelInvalidStateError, BaseAioPikaBrokerError, OSError)

_HIDDEN: Final = "***"


@final
class AmqpTransport(SenderInterface, SetupableTransportInterface, MessageCountAwareInterface):
    """Publishes to one queue, and can declare its topology and count its messages.

    The consume half is the worker the factory builds, which the broker
    drives. Listing messages is not offered: RabbitMQ hands a message out to
    read it, so a queue cannot be looked into without taking from it.

    What publishes is :attr:`sender`; its broker, queue and serializer are
    read here too, as they were when the factory built a sender alone.
    """

    __slots__ = ("_connection", "_name", "_options", "_queue", "_queues", "_sender")

    def __init__(  # noqa: PLR0913 — everything past `sender` is keyword-only
        self,
        sender: TaskiqSender,
        *,
        name: str,
        connection: str,
        options: AmqpOptions,
        queue: str | None,
        queues: Sequence[str],
    ) -> None:
        """Publish through ``sender`` as the transport ``name``.

        Args:
            sender: What publishes the messages.
            name: The transport's name, which errors report.
            connection: The broker's URL, without the transport's settings.
            options: What the transport was configured with.
            queue: The queue this transport reads and writes; the broker's
                default queue when ``None``.
            queues: The queues of the group it was built in, which setting up
                declares — its own alone when the console reaches it by name.
        """
        self._sender = sender
        self._name = name
        self._connection = connection
        self._options = options
        self._queue = queue if queue is not None else Queue().name
        self._queues = tuple(queues)

    @property
    def sender(self) -> TaskiqSender:
        """What publishes this transport's messages."""
        return self._sender

    @property
    def broker(self) -> DelayingBroker:
        """The broker this transport publishes through."""
        return cast("DelayingBroker", self._sender.broker)

    @property
    def queue(self) -> str | None:
        """The queue this transport publishes to, if it pins one."""
        return self._sender.queue

    @property
    def serializer(self) -> SerializerInterface:
        """What this transport encodes messages with."""
        return self._sender.serializer

    @override
    async def send(self, envelope: Envelope) -> Envelope:
        """Publish ``envelope``; see :meth:`TaskiqSender.send`."""
        return await self._sender.send(envelope)

    @override
    async def setup(self) -> None:
        """Declare the exchange, this transport's queues and the dead-letter queue.

        Declared whatever ``auto_setup`` says, which is what lets a deployment
        create its topology once and run with ``auto_setup=false``; a delay
        queue is still declared as a message is delayed. Declaring what exists
        already, as it was declared, changes nothing.

        Raises:
            TransportError: When the broker refuses a declaration or cannot be
                reached.
            InvalidTransportOptionError: When ``delay=native`` meets a broker
                older than RabbitMQ 4.4.
        """
        broker = create_amqp_broker(
            self._connection, replace(self._options, auto_setup=True), self._queues
        )
        try:
            await broker.startup()
        except _BROKER_ERRORS as error:
            # What startup opened is released, without letting its own failure
            # hide the one that matters.
            with contextlib.suppress(*_BROKER_ERRORS):
                await broker.shutdown()
            raise TransportError(self._name, "set up", self._reason(error)) from error
        try:
            await broker.shutdown()
        except _BROKER_ERRORS as error:
            raise TransportError(
                self._name, "close after setting up", self._reason(error)
            ) from error

    @override
    async def count(self) -> int:
        """Return how many messages wait in this transport's queue, ready to be delivered.

        What RabbitMQ reports for the queue: a message held back in a delay
        queue is not counted until it falls due.

        Raises:
            TransportError: When the queue does not exist or the broker cannot
                be reached.
        """
        url = self._options.connection.applied_to(self._connection)
        try:
            connection = await aio_pika.connect(
                url, timeout=self._options.connection.connect_timeout
            )
            async with connection:
                channel = await connection.channel()
                queue = await channel.declare_queue(self._queue, passive=True)
                counted = queue.declaration_result.message_count
        except _BROKER_ERRORS as error:
            raise TransportError(self._name, "count messages", self._reason(error)) from error
        return counted if counted is not None else 0

    def _reason(self, error: BaseException) -> str:
        """Return what ``error`` says, the connection's password left out of it."""
        reason = str(error)
        password = urlsplit(self._connection).password
        if password:
            for written in {password, unquote(password)}:
                reason = reason.replace(written, _HIDDEN)
        return reason
