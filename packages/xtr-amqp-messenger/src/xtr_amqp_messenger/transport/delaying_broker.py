"""A RabbitMQ broker that delays a message with no plugin when the server lets it."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, cast, final, override

from aio_pika import DeliveryMode, ExchangeType, Message
from taskiq_aio_pika import AioPikaBroker
from taskiq_aio_pika.exceptions import IncorrectRoutingKeyError, NoStartupError
from xtr_clock import SystemClock
from xtr_messenger.exception import InvalidTransportOptionError

from .amqp_options import DELAY_AUTO, DELAY_NATIVE, DELAY_PLUGIN, DELAY_QUEUE

if TYPE_CHECKING:
    from taskiq import BrokerMessage
    from taskiq_aio_pika.exchange import Exchange
    from taskiq_aio_pika.queue import Queue
    from xtr_clock import ClockInterface

__all__ = ["DELIVERY_TIME_HEADER", "NATIVE_DELAY_VERSION", "DelayingBroker"]

DELIVERY_TIME_HEADER: Final = "x-opt-delivery-time"
"""The header a quorum queue holds a message back until — a Unix time in milliseconds."""

NATIVE_DELAY_VERSION: Final = (4, 4)
"""The first RabbitMQ whose quorum queues hold a message back by :data:`DELIVERY_TIME_HEADER`."""

_DELAY_LABEL: Final = "delay"
"""The label a delayed send carries its delay in, in seconds — taskiq's own."""

_EXPIRY_MARGIN_MS: Final = 10_000
"""How long a delay queue outlives its delay, so it is never deleted with a message in it."""

_VERSION: Final = re.compile(r"(\d+)\.(\d+)")


@final
class DelayingBroker(AioPikaBroker):
    """Holds a delayed message back natively, in a delay queue, or through the plugin.

    ``delay`` is one of the modes :class:`~.amqp_options.AmqpOptions` reads:
    ``plugin`` is the broker library's own delayed-message exchange, and the
    others are done here, where a message the library would hand to the
    plugin is published instead. ``auto`` is settled once connected, from the
    server's version: natively from RabbitMQ 4.4 on when ``quorum`` — the
    queues being quorum queues — and through delay queues otherwise.

    Retries back off through the same send, so they are delayed the same way.
    """

    def __init__(  # noqa: PLR0913 — what the library's broker takes, all by keyword
        self,
        url: str,
        *,
        qos: int,
        exchange: Exchange,
        task_queues: list[Queue] | None,
        dead_letter_queue: Queue | None,
        delayed_message_exchange: Exchange | None,
        timeout: float | None,
        delay: str,
        quorum: bool,
        clock: ClockInterface | None = None,
    ) -> None:
        """Reach ``url``, delaying as ``delay`` says; the rest is the library broker's own.

        Args:
            url: The server to connect to.
            qos: How many messages a consumer holds unacknowledged.
            exchange: The exchange messages are published through.
            task_queues: The queues consumed and published to.
            dead_letter_queue: Where a message nobody can handle is moved.
            delayed_message_exchange: The plugin's exchange, for ``plugin``.
            timeout: Seconds to wait for the connection to open.
            delay: How to hold a delayed message back.
            quorum: Whether the queues are quorum queues.
            clock: What reads the time a native delay ends at; the system
                clock when left out.
        """
        super().__init__(
            url=url,
            qos=qos,
            exchange=exchange,
            task_queues=task_queues,
            dead_letter_queue=dead_letter_queue,
            delayed_message_exchange_plugin=delay == DELAY_PLUGIN,
            delayed_message_exchange=delayed_message_exchange,
            timeout=timeout,
        )
        self._delay = delay
        self._quorum = quorum
        self._clock: ClockInterface = clock if clock is not None else SystemClock()

    @property
    def delay(self) -> str:
        """How a delayed message is held back — ``auto`` until connected, settled after."""
        return self._delay

    @override
    async def startup(self) -> None:
        """Connect, declare, then settle ``auto`` from the server's version.

        Raises:
            InvalidTransportOptionError: If ``native`` was chosen and the server
                is older than RabbitMQ 4.4, which would ignore the delivery
                time and deliver every delayed message at once.
        """
        await super().startup()
        if self._delay not in {DELAY_AUTO, DELAY_NATIVE}:
            return
        version = _version_of(self.write_conn)
        if self._delay == DELAY_NATIVE:
            if version < NATIVE_DELAY_VERSION:
                await self.shutdown()
                major, minor = version
                reason = f"RabbitMQ 4.4 or later; the server is {major}.{minor}"
                raise InvalidTransportOptionError("delay", DELAY_NATIVE, reason)
            return
        native = self._quorum and version >= NATIVE_DELAY_VERSION
        self._delay = DELAY_NATIVE if native else DELAY_QUEUE

    @override
    async def kick(self, message: BrokerMessage) -> None:
        """Send ``message``, holding it back natively or in a delay queue when it is delayed.

        Raises:
            NoStartupError: If the broker was not started.
            IncorrectRoutingKeyError: If the message names a queue the broker
                does not serve.
        """
        delay = _seconds(message.labels.get(_DELAY_LABEL))
        if delay is None or self._delay not in {DELAY_NATIVE, DELAY_QUEUE}:
            await super().kick(message)
            return
        channel = self.write_channel
        if channel is None:
            raise NoStartupError("Please run startup before kicking.")
        delay_ms = max(round(delay * 1000), 0)
        routing_key = self._routing_key_of(message)
        published = Message(
            body=message.message,
            headers={"task_id": message.task_id, "task_name": message.task_name, **message.labels},
            delivery_mode=DeliveryMode.PERSISTENT,
            priority=_integer(message.labels.get(self._label_for_priority)),
        )
        if self._delay == DELAY_NATIVE:
            now_ms = round(self._clock.now().timestamp() * 1000)
            published.headers[DELIVERY_TIME_HEADER] = now_ms + delay_ms
            exchange = await channel.get_exchange(self._exchange.name, ensure=False)
            _ = await exchange.publish(published, routing_key=routing_key)
            return
        # Declared on every delayed send, never cached: the queue deletes itself
        # once unused, and a message published to a deleted queue is dropped.
        queue = f"{self._exchange.name}.delay.{routing_key}.{delay_ms}"
        _ = await channel.declare_queue(
            queue,
            durable=True,
            arguments={
                "x-message-ttl": delay_ms,
                "x-dead-letter-exchange": self._exchange.name,
                "x-dead-letter-routing-key": routing_key,
                "x-expires": delay_ms + _EXPIRY_MARGIN_MS,
            },
        )
        _ = await channel.default_exchange.publish(published, routing_key=queue)

    def _routing_key_of(self, message: BrokerMessage) -> str:
        """Return the routing key ``message`` is published with, as the library chooses it.

        Raises:
            IncorrectRoutingKeyError: If a direct exchange serves no queue the
                message names.
        """
        queues = self._task_queues
        if len(queues) == 1:
            return queues[0].routing_key or queues[0].name
        named = message.labels.get(self._label_for_routing)
        routing_key = named if isinstance(named, str) else ""
        served = {queue.routing_key or queue.name for queue in queues}
        if self._exchange.type == ExchangeType.DIRECT and routing_key not in served:
            advice = "Check routing keys and queue names in broker queues."
            raise IncorrectRoutingKeyError(f"Routing key '{routing_key}' is not valid. {advice}")
        return routing_key


def _version_of(connection: object) -> tuple[int, int]:
    """Return the major and minor version of the server ``connection`` reached, or ``(0, 0)``."""
    transport = getattr(connection, "transport", None)
    properties = getattr(getattr(transport, "connection", None), "server_properties", None)
    # The server's properties are a field table: whatever the server sent, typed by nothing.
    version = (
        cast("dict[str, object]", properties).get("version")
        if isinstance(properties, dict)
        else None
    )
    matched = _VERSION.match(version if isinstance(version, str) else "")
    return (int(matched[1]), int(matched[2])) if matched is not None else (0, 0)


def _seconds(label: object) -> float | None:
    """Read a delay label, which arrives as text, into seconds."""
    try:
        return float(label) if isinstance(label, (str, int, float)) else None
    except ValueError:
        return None


def _integer(label: object) -> int | None:
    """Read a priority label, which arrives as text, into a number."""
    try:
        return int(label) if isinstance(label, (str, int)) else None
    except ValueError:
        return None
