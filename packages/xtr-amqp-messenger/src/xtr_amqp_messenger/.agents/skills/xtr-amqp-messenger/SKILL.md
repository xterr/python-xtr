---
name: xtr-amqp-messenger
description: How to send and consume xtr-messenger messages through RabbitMQ with xtr-amqp-messenger — amqp and amqps DSNs found with no wiring, queues and exchanges, the retry ladder, delays through the delayed-message exchange, real dead-lettering, TLS settings, scoping a worker to its queues, and building the factory or broker by hand. Use when an application installs xtr-messenger[amqp], configures an amqp transport, sets a retry or dead-letter policy, or needs delays on RabbitMQ.
---

# xtr-amqp-messenger

The RabbitMQ transport of xtr-messenger, built on the bus's taskiq bridge. Installed, an
`amqp://` or `amqps://` DSN is served by `AmqpTransportFactory`, found through its entry point;
it ships no bundle. For buses, routing and workers, load the `xtr-messenger` skill.

## Quick reference

- DSN — `amqp://user:pass@host:5672/vhost?queue=jobs`; `amqps://` for TLS. Credentials
  percent-encoded.
- Settings (query or `options`, `options` wins) — retries `max_attempts`, `base_delay_seconds`,
  `dead_letter_queue`; exchange `exchange`, `exchange_type`, …; queue `queue`, `queue_type`,
  `routing_key`, …; connection `heartbeat`, `connect_timeout`, `connection_name`, …; TLS
  `cacert`, `cert`, `key`, `verify`; consumption `prefetch_count`, `max_async_tasks`,
  `auto_setup`, `delay`. Anything else raises
  `UnknownTransportOptionError`.
- `AmqpTransportFactory(serializer, options=None)` — discovery builds it with the bus's envelope
  serializer.
- Imports — `from xtr_amqp_messenger import AmqpTransportFactory, create_amqp_broker,
  declared_queues, DeadLetterMiddleware, Reliability`; `AmqpOptions` from
  `xtr_amqp_messenger.transport.amqp_options`.

## Configure a transport

```python
from xtr_messenger import MessageBusConfig, TransportConfig

MessageBusConfig(
    transports={
        "jobs": TransportConfig(
            "amqp://guest:guest@rabbit:5672/",
            queue="jobs",
            options={"max_attempts": "5", "dead_letter_queue": "jobs.dlq"},
        ),
        "audit": TransportConfig("amqp://guest:guest@rabbit:5672/", queue="audit"),
    },
    routing={IngestDocument: "jobs"},
)
```

Transports on one DSN share a connection; a worker on `["jobs"]` consumes only that queue.

## Delays and dead letters

A `DelayStamp` and the retry backoff are held back as `delay` says: `auto` (default) delays
natively (`x-opt-delivery-time`) on RabbitMQ 4.4+ quorum queues, else in a TTL delay queue per
delay that dead-letters back — no plugin either way. `delay=native|queue|plugin` forces one;
`plugin` needs `rabbitmq_delayed_message_exchange`. The old `delayed_message_exchange_plugin`
still reads: `true` is `plugin`, `false` is `auto`. A message out of attempts goes to the
configuration's `failure_transport` when one is named (sent by the worker, then acked);
otherwise — and always for a delivery that cannot be decoded — to `dead_letter_queue`
(`taskiq.dlq` by default) in its wire format. `messenger:setup-transports` declares the
exchange, queues and dead-letter queue whatever `auto_setup` says; `messenger:stats` counts a
transport's queue (ready messages only). Listing is not offered: RabbitMQ cannot look into a
queue without taking from it, so point `failure_transport` at a listable one (`orm://`).
The n-th retry waits n times the one before (`base_delay_seconds`, ×2, ×3, …), at most 60 s; a
`DelayStamp`'s delay replaces the base for its message. The dead-letter queue has no
limit: bound it with a RabbitMQ policy (`rabbitmqctl set_policy … '{"max-length": …}'`), never
queue arguments — limits on an existing queue fail with `PRECONDITION_FAILED` at startup. On
RabbitMQ 4+, quorum queues stop a crash-looping message after 20 deliveries by default.

## Build it by hand

```python
from xtr_amqp_messenger import AmqpTransportFactory
from xtr_amqp_messenger.transport.amqp_options import AmqpOptions

MessageBusFactory(config, [AmqpTransportFactory(wire, options=AmqpOptions())]).bus()
```

## Testing

Construct brokers freely: building `AioPikaBroker` opens no connection, so a test can build
senders and workers and inspect them without RabbitMQ. For tests of application code, keep
routing to `in-memory://?serialize=true` and switch the DSN to `amqp://` in production.

## Use in an application

1. `uv add "xtr-messenger[amqp]"` — it installs this package; nothing to activate.
2. In `<app>/config/packages/messenger.py`, name `amqp://` transports — the messenger recipe's
   `MESSENGER_DSN` is one — and route messages to them.
3. Run a worker with `<script> messenger:consume <transport>`.
4. Check with `<script> debug:config messenger` — the `amqp://` transports are listed.

## Errors

- `TransportError` (an `AmqpMessengerError`) — the broker refused `setup()` or `count()`, or
  could not be reached.
- `UnknownTransportOptionError` / `InvalidTransportOptionError` — a setting not accepted, or a
  value not usable; TLS settings on plain `amqp://` are refused too, and `delay=native` for
  queues that are not quorum queues.
- `MixedDsnError` — one worker asked to serve two servers.
- `MissingSerializerError` — the factory discovered with no serializer.

## Do not

- Do not leave `verify=false` on in production: it drops the broker's identity check.
- Do not set `delay=plugin` on a broker without `rabbitmq_delayed_message_exchange`: startup
  fails declaring its exchange.
- Do not build a worker before importing the modules declaring your messages.
