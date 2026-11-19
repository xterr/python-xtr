<div align="center">

# xtr-amqp-messenger

**A RabbitMQ transport for xtr-messenger: queues on an AMQP broker, a retry ladder, delays and real dead-lettering, through taskiq.**

<img alt="python 3.14+" src="https://img.shields.io/badge/python-%E2%89%A5%203.14-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A message bus moves work to another process; RabbitMQ is the broker most deployments already
run. This package is [xtr-messenger](../xtr-messenger)'s transport for it, built on the bus's
broker-agnostic taskiq bridge, and it adds only what is genuinely RabbitMQ:

- 🐇 **`amqp://` and `amqps://`** — found by the bus from the DSN's scheme, with no wiring.
- 🔁 **A retry ladder** — a failed message is tried again, each time later, `max_attempts` times.
- ⏰ **Delays** — a `DelayStamp` rides RabbitMQ's delayed-message exchange.
- ☠️ **Real dead-lettering** — a message out of attempts, or one that can never be handled, is
  republished to a dead-letter queue in its original wire format, never acknowledged and lost.
- 🎯 **One process per workload** — a worker consumes only the queues it is asked to serve.

## Install

```sh
uv add xtr-amqp-messenger
uv add "xtr-messenger[amqp]"   # the same, from the message bus's side
```

It brings xtr-messenger, `taskiq`, `taskiq-aio-pika` and `aio-pika`. It ships no
bundle: the bus finds its factory by the DSN scheme, and the factory needs only the envelope
serializer, which discovery hands over.

## Quick start

```python
from xtr_messenger import MessageBusConfig, MessageBusFactory, TransportConfig, WorkerFactory
from xtr_messenger import JsonSerializer, TransportFactory
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

config = MessageBusConfig(
    transports={"jobs": TransportConfig("amqp://guest:guest@rabbit:5672/", queue="jobs")},
    routing={IngestDocument: "jobs"},
)
wire = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))
factories = [TransportFactory(serializer=wire)]

await MessageBusFactory(config, factories).bus().dispatch(IngestDocument(document_id=1))
await WorkerFactory(config, factories).worker(["jobs"]).run()
```

Import the modules declaring your messages before building a worker: it registers one task per
message declared with `@as_message`, and a message nothing declared cannot be bound.

## Settings

Every setting may go in the DSN's query string or in `TransportConfig.options`; `options` wins.

```python
TransportConfig(
    "amqp://user:pass@rabbit:5672/?queue=jobs&max_attempts=10",
    options={"prefetch_count": "50", "dead_letter_queue": "jobs.dlq"},
)
```

| Group | Settings |
| --- | --- |
| Retries | `max_attempts`, `base_delay_seconds`, `dead_letter_queue` |
| Exchange | `exchange`, `exchange_type`, `exchange_durable`, `exchange_auto_delete` |
| Queue | `queue`, `queue_type`, `queue_durable`, `queue_auto_delete`, `queue_exclusive`, `queue_max_priority`, `routing_key` |
| Connection | `heartbeat`, `connect_timeout`, `connection_name`, `frame_max`, `channel_max` |
| TLS | `cacert`, `cert`, `key`, `verify` |
| Consumption | `prefetch_count`, `max_async_tasks`, `auto_setup`, `delay` |

`max_async_tasks` is how many messages a worker handles at once: ten per CPU, capped at 100,
unless set. A message is acked once handled, so `prefetch_count` (10 by default) caps it too —
a worker handles the smaller of the two at once. Raise both together to go wider.
Each message handled at once may hold a database connection; keep that number within the
pool's size, or the extra handlers wait for a connection.

Delays — a `DelayStamp`, and the retry ladder's backoff — are held back as `delay` says, and
need no plugin by default:

| `delay` | How a delayed message waits |
| --- | --- |
| `auto` (default) | Settled once connected: `native` on RabbitMQ 4.4 and later when the queues are quorum queues, else `queue` |
| `native` | In its own queue, released at the `x-opt-delivery-time` it is sent with; quorum queues of RabbitMQ 4.4 and later only, refused for another `queue_type` |
| `queue` | In a queue of its own for that delay — `<exchange>.delay.<routing key>.<ms>`, with that TTL — which dead-letters it back to its exchange and routing key; works on any RabbitMQ. The queue is declared as a message is delayed, `auto_setup` or not, and deletes itself 10 s after its last use |
| `plugin` | Through the delayed-message exchange of the `rabbitmq_delayed_message_exchange` plugin, which must be enabled on the broker |

`delayed_message_exchange_plugin`, the setting this replaced, still reads when `delay` is not
given: `true` is `delay=plugin`, `false` is `delay=auto`.

The TLS settings belong to `amqps://` and are refused on plain `amqp://`, where the driver
would silently ignore them. `verify=false` is warned about once per factory — a notice, not a
per-broker drumbeat. `connect_timeout` is passed to the driver's connect call, where it is
read; `heartbeat` takes whole seconds and refuses values below one, which the driver would
read as "no heartbeat at all".

An unrecognised setting is refused with `UnknownTransportOptionError`, naming what the scheme
does accept, and a value it cannot use — `prefetch_count=lots` — with
`InvalidTransportOptionError`. Credentials stay in the DSN, percent-encoded.

## Retries and dead-lettering

The bus's own worker makes one attempt per message; here taskiq's worker runs the message, and
the transport decides what a failure means. A failed message is retried until `max_attempts`,
each retry waiting n times as long as the one before it — `base_delay_seconds`, then twice
that, then three times the second, at most 60 seconds; then it is republished to
`taskiq.dlq` — or the
`dead_letter_queue` you name — in its original wire format, so it can be inspected and
replayed. A handler asking for the envelope reads which attempt it is on in its
`RedeliveryStamp`.
A message sent with a `DelayStamp` carries that delay into its retries: its first retry waits as
long as the stamp asked, not `base_delay_seconds`.
A retry is a new copy published before the failed delivery is acked, so a worker dying between
the two leaves both: handlers must be idempotent.

With a dead-letter queue configured, a delivery that can never be handled — unparsable, naming
a task nobody registered, or whose body does not decode into its message — is quarantined there
at once rather than retried.

The dead-letter queue is declared with no length or delivery limit, so it grows until someone
drains it. Bound it with a RabbitMQ policy rather than queue arguments: declaring limits on a
queue that already exists without them fails with `PRECONDITION_FAILED`, at startup, on every
deployment that has one.

```sh
rabbitmqctl set_policy dlq-bound '^taskiq\.dlq$' \
  '{"max-length": 100000, "overflow": "drop-head"}' --apply-to queues
```

On RabbitMQ 4 and later a quorum queue (`queue_type=quorum`) already stops redelivering a message
that crashes its worker after 20 deliveries — its default delivery limit — and drops it, or
dead-letters it when the queue has a dead-letter exchange.

Transports sharing a DSN but naming different queues share one connection, and a worker
consumes exactly the queues of the transports it is asked for, so one deployment can run a
process per workload. One worker serving two servers is refused with `MixedDsnError`.

Warnings — `verify=false`, a poison delivery dead-lettered — go to the standard library's
`logging.getLogger("messenger")`, beside the rest of the bus's output; a poison delivery's
reason is logged, never its body.

## Building it yourself

A factory given a collaborator discovery cannot supply is passed to the bus directly:

```python
from xtr_amqp_messenger import AmqpTransportFactory
from xtr_amqp_messenger.transport.amqp_options import AmqpOptions

MessageBusFactory(config, [AmqpTransportFactory(wire, options=AmqpOptions(...))]).bus()
```

`create_amqp_broker` builds a configured `AioPikaBroker` — retry ladder, delayed-message
exchange and dead-lettering wired — and `declared_queues(broker)` names the queues it consumes.

## Use in an application

Everything adding this package to an application takes — and, read backwards, what removing it
undoes. It ships no bundle: the message bus finds its factory by the DSN scheme.

- **Install** — `uv add xtr-amqp-messenger`, or `uv add "xtr-messenger[amqp]"`, beside
  xtr-messenger set up as its
  [*Use in an application*](../xtr-messenger/README.md#use-in-an-application) says.
- **Recipe** — `uv run xtr-recipes recipes:sync` writes nothing: there is no bundle to list, no
  configuration file, environment variable or ignore line. The messenger's own recipe writes
  `MESSENGER_DSN`, a RabbitMQ one.
- **Configure** — name `amqp://` transports in `<app>/config/packages/messenger.py` and route
  messages to them. Delays need nothing on the broker; `delay=plugin` uses the
  `rabbitmq_delayed_message_exchange` plugin where it is enabled.
- **Run** — a worker is `<script> messenger:consume <transport>`.
- **Remove** — drop the `amqp://` transports and the routing to them, then
  `uv remove xtr-amqp-messenger`.
- **Check** — `debug:config messenger` lists the `amqp://` transports.

## Errors

Everything raised derives from xtr-messenger's `MessageBusError`:

| Error | Raised when |
| --- | --- |
| `UnknownTransportOptionError`, `InvalidTransportOptionError` | A setting is not accepted, or its value is not usable |
| `MixedDsnError` | One worker is asked to serve transports on two servers |
| `MissingSerializerError` | The factory is discovered with no envelope serializer to build it with |

## Upgrading

What changes for an application moving to 7.0, and how to keep the old behaviour where that is
still possible: [Upgrading to 7.0](../../UPGRADING.md#xtr-amqp-messenger).

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-amqp-messenger`; run the commands below from there. The `python-xtr-amqp-messenger`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

No broker is needed: every test runs on brokers that open no connection.

## License

MIT — see [LICENSE](LICENSE).
