"""Building a RabbitMQ broker with retries, delays and dead-lettering wired up.

Use this factory rather than constructing ``AioPikaBroker`` directly: it is
where the retry ladder, the delayed-message exchange and real dead-lettering
are wired. A hand-built broker gets none of them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from aio_pika import ExchangeType
from taskiq import SmartRetryMiddleware
from taskiq_aio_pika.exchange import Exchange
from taskiq_aio_pika.queue import Queue

from .amqp_options import DELAY_PLUGIN, AmqpOptions
from .dead_letter_middleware import DeadLetterMiddleware
from .delaying_broker import DelayingBroker

if TYPE_CHECKING:
    from collections.abc import Sequence

    from taskiq_aio_pika import AioPikaBroker
    from xtr_clock import ClockInterface

__all__ = ["create_amqp_broker", "declared_queues"]

_MAX_DELAY_SECONDS: Final = 60.0


def create_amqp_broker(
    url: str,
    options: AmqpOptions | None = None,
    queues: Sequence[str] = (),
    clock: ClockInterface | None = None,
) -> AioPikaBroker:
    """Build a RabbitMQ broker.

    Construction opens no connection, so this is safe to call at import time
    — which is what a module-level broker in a worker entrypoint needs.

    Pass ``queues`` to publish to more than one queue; a
    :class:`~xtr_messenger.bridge.taskiq.taskiq_sender.TaskiqSender` then
    selects one by name, which is how a routing table maps message types onto
    queues.

    A delayed message is held back as ``options.delay`` says — natively on
    RabbitMQ 4.4 and later, in a delay queue of its own on an older one, by
    default; ``clock`` reads the time a native delay ends at. With
    ``auto_setup`` off nothing is declared but delay queues, the dead-letter
    queue and the plugin's delayed exchange included: the topology must
    already exist, or startup fails naming what is missing.
    """
    configured = options if options is not None else AmqpOptions()
    settings = configured.reliability
    plugin = configured.delay == DELAY_PLUGIN
    broker = DelayingBroker(
        url=configured.connection.applied_to(url),
        qos=configured.prefetch_count,
        exchange=configured.exchange.declared(configured.auto_setup),
        task_queues=[configured.queue.declared(name, configured.auto_setup) for name in queues]
        or None,
        dead_letter_queue=(
            Queue(name=settings.dead_letter_queue, declare=configured.auto_setup)
            if settings.dead_letter_queue is not None
            else None
        ),
        delayed_message_exchange=_delayed_exchange(configured) if plugin else None,
        # The driver only honours the connect timeout as a call argument —
        # as a URL parameter it is ignored — so it travels beside the URL.
        timeout=configured.connection.connect_timeout,
        delay=configured.delay,
        quorum=configured.uses_quorum_queues,
        clock=clock,
    ).with_middlewares(
        SmartRetryMiddleware(
            default_retry_count=settings.max_attempts,
            default_delay=settings.base_delay_seconds,
            use_delay_exponent=True,
            max_delay_exponent=_MAX_DELAY_SECONDS,
            default_retry_label=True,
        ),
    )
    if settings.dead_letter_queue is not None:
        return broker.with_middlewares(
            DeadLetterMiddleware(settings.dead_letter_queue, settings.max_attempts),
        )
    return broker


def _delayed_exchange(configured: AmqpOptions) -> Exchange:
    """Return the delayed-message exchange, declared only under ``auto_setup``.

    The broker library's own default always declares it, which a deployment
    that owns its topology has no permission for — so the same exchange is
    built here with the declare flag the configuration chose.
    """
    name = configured.exchange.name if configured.exchange.name is not None else Exchange().name
    return Exchange(
        name=f"{name}.plugin_delay",
        type=ExchangeType.X_DELAYED_MESSAGE,
        arguments={"x-delayed-type": "direct"},
        declare=configured.auto_setup,
    )


def declared_queues(broker: AioPikaBroker) -> tuple[str, ...]:
    """Return the queues ``broker`` declares, which are the ones it consumes.

    Useful at worker startup to log the workload a process has taken on, and
    to confirm a deployment scoped its workers the way it intended.
    """
    # Taskiq exposes the declared queues nowhere else.
    return tuple(queue.name for queue in broker._task_queues)  # noqa: SLF001 — no public accessor
