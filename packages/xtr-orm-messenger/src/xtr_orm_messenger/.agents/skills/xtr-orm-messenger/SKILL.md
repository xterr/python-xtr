---
name: xtr-orm-messenger
description: How to queue xtr-messenger messages in a database table with xtr-orm-messenger — an orm DSN naming an xtr-orm connection, OrmTransportFactory and its bundle, queues, delays, redelivery of messages a dead worker held, PostgreSQL notifications, sending in the unit of work's transaction, the messages table in migrations, and counting, listing or finding queued messages. Use when an application wants a message queue without a broker, configures an orm transport, routes messages to the database, runs a worker on a table, maps the messenger_messages table into migrations, or tests code that sends through the orm transport.
---

# xtr-orm-messenger

A transport for xtr-messenger whose messages live in a table on a connection xtr-orm
configures. For buses, routing and workers load the `xtr-messenger` skill; for connections and
migrations, `xtr-orm`.

## Quick reference

- DSN — `orm://<connection>`, `orm://` for the default connection; queue with
  `TransportConfig(dsn, queue="jobs")` or `?queue=jobs`, `default` otherwise.
- Options (DSN query or `options`) — `table_name` (`messenger_messages`), `redeliver_timeout`
  (`3600` s), `auto_setup` (`true`), `poll_interval` (`1.0` s), `transactional` (`false`),
  `use_notify` (`true`), `check_delayed_interval` / `get_notify_timeout` (`60000` ms).
- `OrmTransportFactory(registry, serializer, clock=None)` — not discovered by scheme: the
  bundle registers it with the messenger's envelope serializer, or you pass it to
  `MessageBusFactory` / `WorkerFactory`.
- Settling deletes the row; a row handed out longer than `redeliver_timeout` is claimed again.
- A `DelayStamp` makes the message due later, rounded up to a whole second.

## Send and consume without a container

```python
from xtr_messenger import (
    JsonSerializer,
    MessageBusConfig,
    MessageBusFactory,
    TransportConfig,
    WorkerFactory,
)
from xtr_orm import ConnectionRegistry
from xtr_orm_messenger import OrmTransportFactory
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

registry = ConnectionRegistry()
registry.register("default", engine=engine, migrator=migrator, database=database)
wire = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))
factory = OrmTransportFactory(registry, wire)
config = MessageBusConfig(
    transports={"jobs": TransportConfig("orm://default", queue="jobs")},
    routing={IngestDocument: "jobs"},
)

await MessageBusFactory(config, [factory]).bus().dispatch(IngestDocument(document_id=1))
await WorkerFactory(config, [factory]).worker(["jobs"]).run()
```

Pass the same factory to the bus and the worker: it keeps one transport per name.

## Send with the handler's changes

`TransportConfig("orm://default?transactional=true")` writes the message in the session of the
unit of work under way, so it is sent only when that unit commits. List `orm_transaction` in the
bus middleware, or commit the session yourself; outside a unit the message commits at once.

## Look into a queue

```python
transport = factory.transport("jobs", config.transports["jobs"])
await transport.count()
messages = [envelope async for envelope in transport.all(limit=10)]
await transport.find(message_id)
await transport.keepalive(envelope, seconds=600)  # a handler running past redeliver_timeout
```

## Testing

Run against a SQLite file per test (`sqlite+aiosqlite:///{tmp_path / 'app.sqlite'}`) and freeze
a `MockClock`: `OrmTransportFactory(registry, wire, clock=clock)` makes delays and redelivery happen
when the test moves the clock. A worker's `get()` never runs dry — stop the worker from a
handler, or run it in a task and call `stop()`. `in-memory://` stays the transport for tests that
do not care where messages are kept.

## Use in an application

1. `uv run xtr-recipes recipes:add xtr-orm-messenger` — or `"xtr-orm-messenger[postgres]"` for
   PostgreSQL through asyncpg. It lists `OrmMessengerBundle`, which brings the messenger and orm
   bundles.
2. In `<app>/config/packages/messenger.py`, name a transport `orm://default` and route messages
   to it.
3. Optional: return `OrmMessengerConfig(migrations_connection="default")` from
   `<app>/config/packages/orm_messenger.py`, add `auto_setup=false` to the DSN, and run
   `orm:migrations:diff` — the table joins that connection's migrations.
4. Run a worker with `<script> messenger:consume <transport>`.
5. Check with `<script> debug:bundles` — `orm_messenger` active, `messenger` and `orm` required.

## Errors

- `OrmMessengerError` — the base, itself a `MessageBusError`.
- `TransportError` — the database refused a send, claim, settle or listing, or an envelope was
  settled on a transport it was not received from; `transport`, `operation`, `reason`.
- `InvalidOrmDsnError` — the DSN names a connection the registry does not hold; a `LookupError`.
- `UnknownTransportOptionError` / `InvalidTransportOptionError` — from xtr-messenger, for a
  setting the transport does not take or a value it cannot read.

## Do not

- Do not put a database URL in the DSN: it names a connection, configured in the orm.
- Do not rely on `transactional=true` without something committing the unit's session.
- Do not set `redeliver_timeout` below the time a handler takes, unless it calls `keepalive`.
- Do not expect notifications through a PostgreSQL driver other than asyncpg: it polls.
