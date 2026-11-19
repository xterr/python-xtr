"""The settings an AMQP transport reads from its configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from xtr_messenger.bridge.taskiq.taskiq_worker import default_max_async_tasks
from xtr_messenger.exception import InvalidTransportOptionError
from xtr_messenger.transport.transport_options import as_bool, as_choice, as_int

from .connection_options import CONNECTION_OPTIONS, ConnectionOptions
from .exchange_options import EXCHANGE_OPTIONS, ExchangeOptions
from .queue_options import QUEUE_OPTIONS, QueueOptions
from .reliability import RELIABILITY_OPTIONS, Reliability

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "AMQP_OPTIONS",
    "DELAY_AUTO",
    "DELAY_MODES",
    "DELAY_NATIVE",
    "DELAY_PLUGIN",
    "DELAY_QUEUE",
    "AmqpOptions",
]

DELAY_AUTO: Final = "auto"
"""Pick how to delay once connected: natively on RabbitMQ 4.4 and later, else through queues."""

DELAY_NATIVE: Final = "native"
"""Delay in the queue itself, which quorum queues do from RabbitMQ 4.4 on."""

DELAY_PLUGIN: Final = "plugin"
"""Delay through the exchange the ``rabbitmq_delayed_message_exchange`` plugin provides."""

DELAY_QUEUE: Final = "queue"
"""Delay in a queue of its own per delay, dead-lettering back once it expires."""

DELAY_MODES: Final = (DELAY_AUTO, DELAY_NATIVE, DELAY_PLUGIN, DELAY_QUEUE)
"""Every value the ``delay`` setting takes."""

_QUORUM: Final = "quorum"

#: Every setting an ``amqp://`` transport accepts, from its DSN query string
#: or its ``options``. Anything else is rejected rather than ignored.
AMQP_OPTIONS: Final = (
    "prefetch_count",
    "max_async_tasks",
    "auto_setup",
    "delay",
    "delayed_message_exchange_plugin",
    *RELIABILITY_OPTIONS,
    *EXCHANGE_OPTIONS,
    *QUEUE_OPTIONS,
    *CONNECTION_OPTIONS,
)

_DEFAULT_PREFETCH: Final = 10


@dataclass(frozen=True, slots=True)
class AmqpOptions:
    """What an ``amqp://`` transport was configured with.

    Grouped by what they configure. Credentials are absent on purpose: they
    travel in the DSN itself, where a URL already expresses them.

    Attributes:
        reliability: How hard to retry, and where exhausted messages go.
        exchange: The exchange messages are published through.
        queue: How each named queue is declared.
        connection: How the driver opens and keeps the connection.
        prefetch_count: How many messages a consumer may hold unacked. The
            lever for throughput against fair distribution across workers.
        max_async_tasks: How many messages a worker handles at once. Ten per
            CPU, capped at 100, unless configured. A message is acked once
            handled, so ``prefetch_count`` caps this too: a worker handles
            the smaller of the two at once.
        auto_setup: Whether to declare the exchange and queues on startup.
            Turn it off where a deployment creates its own topology and the
            application has no permission to.
        delay: How a delayed message — a
            :class:`~xtr_messenger.stamp.DelayStamp`, or a retry backing off —
            is held back. ``auto`` decides once connected: ``native`` on
            RabbitMQ 4.4 and later when the queues are quorum queues, else
            ``queue``. ``native`` sets the delivery time on the message, which
            only quorum queues of RabbitMQ 4.4 and later honour. ``plugin``
            publishes through the delayed-message exchange, which needs the
            ``rabbitmq_delayed_message_exchange`` plugin. ``queue`` parks the
            message in a queue of its own for that delay, which dead-letters
            it back to its exchange once it expires — on any RabbitMQ, with
            no plugin; each such queue is declared as a message is delayed,
            ``auto_setup`` or not, and deletes itself once unused.
    """

    reliability: Reliability = field(default_factory=Reliability)
    exchange: ExchangeOptions = field(default_factory=ExchangeOptions)
    queue: QueueOptions = field(default_factory=QueueOptions)
    connection: ConnectionOptions = field(default_factory=ConnectionOptions)
    prefetch_count: int = _DEFAULT_PREFETCH
    max_async_tasks: int = field(default_factory=default_max_async_tasks)
    auto_setup: bool = True
    delay: str = DELAY_AUTO

    def __post_init__(self) -> None:
        """Refuse a ``max_async_tasks`` meaning no limit, and a delay the queues cannot hold.

        Validated on the object rather than only when reading settings, so a
        value built in code is checked too, and the error is this package's
        own rather than a ``KeyError`` from a value that never came from the
        settings.

        Raises:
            InvalidTransportOptionError: If ``max_async_tasks`` is below one,
                ``delay`` is not one of :data:`DELAY_MODES`, or it is
                ``native`` for queues that are not quorum queues.
        """
        if self.max_async_tasks < 1:
            raise InvalidTransportOptionError(
                "max_async_tasks", str(self.max_async_tasks), "a whole number above zero"
            )
        if self.delay not in DELAY_MODES:
            raise InvalidTransportOptionError("delay", self.delay, f"one of {DELAY_MODES}")
        if self.delay == DELAY_NATIVE and not self.uses_quorum_queues:
            raise InvalidTransportOptionError(
                "delay", self.delay, "quorum queues, the only ones that delay natively"
            )

    @property
    def uses_quorum_queues(self) -> bool:
        """Tell whether the queues are quorum queues, the only ones that delay natively."""
        return self.queue.type == _QUORUM

    @classmethod
    def from_settings(
        cls,
        settings: Mapping[str, str],
        defaults: AmqpOptions | None = None,
    ) -> AmqpOptions:
        """Read every option out of a transport's settings.

        Anything the settings do not mention keeps its value from
        ``defaults``, so a factory built with a policy in code can still have
        one setting overridden per transport.

        ``delayed_message_exchange_plugin`` is read when ``delay`` is not
        given: ``true`` is ``delay=plugin``, ``false`` is ``delay=auto``.

        Raises:
            InvalidTransportOptionError: If a value is present but not usable.
        """
        base = defaults if defaults is not None else cls()
        delay = base.delay
        if "delay" in settings:
            delay = as_choice(settings, "delay", DELAY_MODES, base.delay)
        elif "delayed_message_exchange_plugin" in settings:
            plugin = as_bool(settings, "delayed_message_exchange_plugin")
            delay = DELAY_PLUGIN if plugin else DELAY_AUTO
        return cls(
            reliability=Reliability.from_settings(settings, base.reliability),
            exchange=ExchangeOptions.from_settings(settings, base.exchange),
            queue=QueueOptions.from_settings(settings, base.queue),
            connection=ConnectionOptions.from_settings(settings, base.connection),
            prefetch_count=as_int(settings, "prefetch_count", base.prefetch_count),
            max_async_tasks=as_int(settings, "max_async_tasks", base.max_async_tasks),
            auto_setup=as_bool(settings, "auto_setup", base.auto_setup),
            delay=delay,
        )
