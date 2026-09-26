"""The message bus: transports, routing, middleware — every ``MessageBusConfig`` field.

dev/test run entirely in process — ``sync://``, ``in-memory://`` and the application's own
``outbox://``. prod routes through RabbitMQ; its DSN is an ``env()`` placeholder, read only
when the bus is built, so building (and even running) a prod kernel that never dispatches
needs no broker.
"""

from __future__ import annotations

from dataclasses import replace

from xtr_dependency_injection import configure, env, when
from xtr_messenger.bundle import MessageBusConfig, TransportConfig

from bookshop.messaging.messages import PlaceOrder, SendReceipt
from bookshop.messaging.middleware import MaintenanceGuard

__all__ = ["messenger", "messenger_prod", "messenger_timing"]


@configure
def messenger() -> MessageBusConfig:
    """Dev and test: nothing leaves the process."""
    return MessageBusConfig(
        transports={
            # Handled during the dispatch, in the calling process.
            "sync": TransportConfig("sync://"),
            # Recorded, and drained by a worker; ?serialize=true round-trips every message
            # through the serializer, so what would fail on a real broker fails here.
            "jobs": TransportConfig("in-memory://?serialize=true"),
            # The same setting given through ``options`` instead of the query string.
            "audit": TransportConfig("in-memory://", options={"serialize": "true"}),
            # The application's own scheme; ``queue`` is available to any transport.
            "outbox": TransportConfig("outbox://local", queue="purchasing"),
        },
        routing={
            PlaceOrder: "sync",
            SendReceipt: ["jobs", "audit"],  # fan-out: one message, two transports
        },
        # In order, ahead of routing and handling: names resolved from the container, and
        # an instance used as it is. ``env(..., bool, ...)`` is resolved before the bus
        # receives the config.
        middleware=[
            "logging",
            "audit_trail",
            MaintenanceGuard(enabled=env("SHOP_MAINTENANCE", bool, default=False)),
        ],
        default_middleware=True,
        require_sender=False,
        # AuditEvent is routed nowhere: handle it here rather than let it pass quietly.
        handle_unrouted=True,
    )


@configure
@when("prod")
def messenger_prod() -> MessageBusConfig:
    """prod: RabbitMQ. A ``@when`` base wins over the unconditional one above.

    Every AMQP setting may go in the DSN's query string or in ``options``; ``options`` wins.
    An unknown one is refused (``UnknownTransportOptionError``), a bad value too
    (``InvalidTransportOptionError``) — when the transport is built.
    """
    dsn = env("MESSENGER_TRANSPORT_DSN")
    return MessageBusConfig(
        transports={
            "sync": TransportConfig("sync://"),
            "jobs": TransportConfig(
                dsn,
                queue="bookshop.jobs",
                options={
                    "max_attempts": "5",
                    "base_delay_seconds": "2",
                    "dead_letter_queue": "bookshop.jobs.dlq",
                    "prefetch_count": "20",
                    "max_async_tasks": "20",
                    "exchange": "bookshop",
                    "exchange_type": "direct",
                    "queue_durable": "true",
                    "connection_name": "bookshop",
                    "heartbeat": "30",
                },
            ),
            # Same server, another queue: the two transports share one connection.
            "audit": TransportConfig(dsn, queue="bookshop.audit"),
            "outbox": TransportConfig(dsn, queue="bookshop.purchasing"),
        },
        routing={
            PlaceOrder: "sync",
            SendReceipt: ["jobs", "audit"],
            "*": "audit",  # catch-all: everything else, AuditEvent included
        },
        middleware=["logging", "audit_trail"],
        require_sender=True,
        handle_unrouted=False,
    )


@configure(priority=-10)
def messenger_timing(config: MessageBusConfig) -> MessageBusConfig:
    """A transform, in every environment: append the timing middleware, under its alias name.

    It receives whichever base won, and runs after the other transforms (lower priority).
    """
    return replace(config, middleware=(*config.middleware, "stopwatch"))
