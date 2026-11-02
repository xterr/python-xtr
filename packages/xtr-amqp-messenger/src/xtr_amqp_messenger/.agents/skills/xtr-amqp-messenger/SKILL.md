---
name: xtr-amqp-messenger
description: How to send and consume xtr-messenger messages through RabbitMQ with xtr-amqp-messenger — amqp and amqps DSNs found with no wiring, queues and exchanges, the retry ladder, delays through the delayed-message exchange, real dead-lettering, TLS settings, scoping a worker to its queues, and building the factory or broker by hand. Use when an application installs xtr-messenger[amqp], configures an amqp transport, sets a retry or dead-letter policy, needs delays on RabbitMQ, or moves imports off xtr_messenger.bridge.amqp.
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
  `auto_setup`, `delayed_message_exchange_plugin`. Anything else raises
  `UnknownTransportOptionError`.
- `AmqpTransportFactory(serializer, options=None)` — discovery builds it with the bus's envelope
  serializer.
- Imports — `from xtr_amqp_messenger import AmqpTransportFactory, create_amqp_broker,
  declared_queues, DeadLetterMiddleware, Reliability`; `AmqpOptions` from
  `xtr_amqp_messenger.transport.amqp_options`. `xtr_messenger.bridge.amqp` still works, as the
  same objects, for this major version.

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

A `DelayStamp` and the retry backoff ride the `rabbitmq_delayed_message_exchange` plugin. On a
broker without it, add `delayed_message_exchange_plugin=false` and `max_attempts=1`; a delayed
send is then refused with `UnsupportedStampError`. A message out of attempts — or one that can
never be handled — goes to `dead_letter_queue` (`taskiq.dlq` by default) in its wire format.

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
3. Enable `rabbitmq_delayed_message_exchange` on the broker, or add
   `delayed_message_exchange_plugin=false` to the DSN.
4. Run a worker with `<script> messenger:consume <transport>`.
5. Check with `<script> debug:config messenger` — the `amqp://` transports are listed.

## Errors

- `UnknownTransportOptionError` / `InvalidTransportOptionError` — a setting not accepted, or a
  value not usable; TLS settings on plain `amqp://` are refused too.
- `UnsupportedStampError` — a delay with the delayed-message plugin turned off.
- `MixedDsnError` — one worker asked to serve two servers.
- `MissingSerializerError` — the factory discovered with no serializer.

## Do not

- Do not import from `xtr_messenger.bridge.amqp` in new code: it goes in the next major version.
- Do not leave `verify=false` on in production: it drops the broker's identity check.
- Do not expect a delay without the delayed-message plugin: the send is refused, not sent early.
- Do not build a worker before importing the modules declaring your messages.
