<div align="center">

# xtr-orm-messenger

**A database transport for xtr-messenger: messages kept in a table on an xtr-orm connection, claimed by workers, delayed, redelivered and woken by notifications.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A queue needs a broker, and a broker is one more server to run, back up and watch. An
application that already has a database can keep its messages there: in a table, on the
connection [xtr-orm](../xtr-orm) already configures, sent in the same transaction as the
changes they announce if it wants.

- 🗄️ **No broker** — `orm://default` is the application's own `default` connection.
- 🔒 **Workers never collide** — each claims the oldest due message `FOR UPDATE SKIP LOCKED`.
- ⏰ **Delays** — a `DelayStamp` makes a message due later.
- ♻️ **Nothing is lost to a dead worker** — a message never settled is handed out again.
- 🔔 **No polling on PostgreSQL** — a waiting worker is woken the moment a message is sent.
- 🤝 **Sent with the handler's changes** — `transactional=true` writes the message in the unit
  of work's session, so it commits or rolls back with them.

## Install

```sh
uv add xtr-orm-messenger
uv add "xtr-orm-messenger[postgres]"   # PostgreSQL through asyncpg, notifications included
```

It needs [xtr-messenger](../xtr-messenger) and [xtr-orm](../xtr-orm), which come with it; the
database driver is xtr-orm's extra (`postgres`, `mysql`, `sqlite`).

## Quick start

Without a container, hand the factory the connections it builds on and the envelope serializer
the bus and its workers share:

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

config = MessageBusConfig(
    transports={"jobs": TransportConfig("orm://default", queue="jobs")},
    routing={IngestDocument: "jobs"},
)
wire = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))
factory = OrmTransportFactory(registry, wire)

await MessageBusFactory(config, [factory]).bus().dispatch(IngestDocument(document_id=1))
await WorkerFactory(config, [factory]).worker(["jobs"]).run()
```

The bus writes the message into `messenger_messages`; the worker claims it, hands it to its
handlers and deletes it. With the [bundle](#kernel--bundle) all of that is wired for you.

## How it works

| Step | What happens |
| --- | --- |
| Send | One row: the encoded envelope, its queue, `created_at`, and `available_at` — later by the delay, rounded up to a whole second |
| Claim | In one transaction, the oldest row of the queue that is due and not handed out is selected `FOR UPDATE SKIP LOCKED` and stamped `delivered_at` |
| Handle | The worker dispatches it; the envelope carries `OrmReceivedStamp` and `TransportMessageIdStamp`, both the row's id |
| Settle | Acknowledged or rejected, the row is deleted |
| Redeliver | A row handed out more than `redeliver_timeout` seconds ago is claimable again: its worker is taken for dead |

A worker that finds nothing due waits `poll_interval` seconds before asking again. On
PostgreSQL through asyncpg it listens instead: every send announces itself on the table's
channel, naming its queue, and the worker asks again at once — or after
`check_delayed_interval`, for a delayed message falling due. Listening holds one connection of
the pool for as long as the worker runs.

SQLite has no row locks, so the lock clause is left out there. A second worker reaching for the
row another is claiming gets "database is locked", which counts as a conflict and is tried again.

Conflicts between workers — a deadlock, a lock wait that timed out — say nothing about the
message. A poll sits through 3 in a row before it raises; an acknowledgement or a rejection
tries again with a pause doubling from 100 ms. One whose database went away waits up to 5
seconds for it and is replayed once: losing an acknowledgement to a restart would hand the
message out again.

A message that does not decode can never be handled, so it is rejected at once, its reason
logged on the `messenger` logger — never its body.

## Options

Every option may go in the DSN's query string or in `TransportConfig.options`; `options` wins.
An unknown one is refused with `UnknownTransportOptionError`, a bad value with
`InvalidTransportOptionError`.

| Option | Default | What it sets |
| --- | --- | --- |
| `queue` | `default` | the queue this transport reads and writes; also `TransportConfig(queue=...)` |
| `table_name` | `messenger_messages` | the table, a plain identifier |
| `redeliver_timeout` | `3600` | seconds after which a message handed out and never settled is handed out again |
| `auto_setup` | `true` | create the table the first time an operation finds it missing |
| `poll_interval` | `1.0` | seconds a worker waits before asking again when nothing was due |
| `transactional` | `false` | write the message in the session of the unit of work under way |
| `use_notify` | `true` | on PostgreSQL through asyncpg, wait for notifications instead of polling |
| `check_delayed_interval` | `60000` | milliseconds a listening worker waits at most before asking anyway |
| `get_notify_timeout` | `60000` | milliseconds one wait for a notification lasts at most |

`orm://` with no name uses the default connection. A name the application did not configure is
refused with `InvalidOrmDsnError` when the transport is built.

### Sending with the handler's changes

With `transactional=true`, a message dispatched while a message is handled — or a request, or a
command: any unit of work — is written in that unit's session and sent only when the unit
commits. Run the `orm_transaction` middleware, or commit yourself: a session never commits on
its own. Outside a unit of work the message is written in a transaction of its own, as it is
without the option.

## Looking into a queue

`OrmTransport` is a `TransportInterface` with more to ask:

```python
transport = factory.transport("jobs", config.transports["jobs"])

await transport.count()  # what a worker could claim now
async for envelope in transport.all(limit=10):
    ...  # the same, oldest first
await transport.find(message_id)  # one message, handed out or not
await transport.keepalive(envelope, seconds=600)  # a long handler keeps its message
await transport.setup()  # create the table ahead of time
```

`keepalive` restarts a message's redelivery clock; `seconds` is how long until the next call,
refused when longer than `redeliver_timeout`.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-orm-messenger`, or `uv add "xtr-orm-messenger[postgres]"` for
  PostgreSQL through asyncpg, the driver notifications go through. The database the transport
  writes to is a connection [xtr-orm](../xtr-orm) configures.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below: it lists
  `OrmMessengerBundle`. There is no configuration file, environment variable or ignore line to
  write; it prints the step naming a transport, which a recipe cannot make for you.
- **Activate** — `OrmMessengerBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`,
  imported from `xtr_orm_messenger.bundle`.
- **Brings along** — the messenger and the orm bundles, always: the transport is for the one and
  built on the other.
- **Configure** — nothing is required: name a transport `orm://default` in the message bus
  configuration, `<app>/config/packages/messenger.py`, and route messages to it. The transport
  creates its table the first time it runs. To have `orm:migrations:diff` write the table
  instead, return `OrmMessengerConfig(migrations_connection="default")` from a `@configure`
  function in `<app>/config/packages/orm_messenger.py` and turn `auto_setup` off — see
  [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing: the DSN names a connection, whose URL the orm reads.
- **Ignore** — nothing.
- **Run** — a worker is `<script> messenger:consume <transport>`.
- **Remove** — drop the `orm://` transports and the routing to them, drop the `BUNDLES` entry and
  `<app>/config/packages/orm_messenger.py`; a migration dropping the table, if a revision wrote
  it. Then `uv remove xtr-orm-messenger`.
- **Check** — `debug:bundles` shows `orm_messenger` as `listed` and `active`, and `messenger` and
  `orm` as `required`.

## Kernel / bundle

```python
# app/config/bundles.py
from xtr_orm_messenger.bundle import OrmMessengerBundle

BUNDLES = {OrmMessengerBundle: {"all": True}}
```

```python
# app/config/packages/messenger.py
from xtr_dependency_injection import configure
from xtr_messenger.bundle import MessageBusConfig, TransportConfig


@configure
def messenger() -> MessageBusConfig:
    return MessageBusConfig(
        transports={"jobs": TransportConfig("orm://default?auto_setup=false", queue="jobs")},
        routing={IngestDocument: "jobs"},
    )
```

```python
# app/config/packages/orm_messenger.py
from xtr_dependency_injection import configure
from xtr_orm_messenger.bundle import OrmMessengerConfig


@configure
def orm_messenger() -> OrmMessengerConfig:
    return OrmMessengerConfig(migrations_connection="default")
```

The bundle registers `OrmTransportFactory` with the messenger, built on the orm's
`ConnectionRegistry` and the messenger's envelope serializer, and consulted ahead of the
factories found by DSN scheme. A bus and every worker of the container share it, and so share
each transport. When the kernel shuts down, the connections workers listened on are given back.

`OrmMessengerConfig` is a frozen dataclass buildable with no arguments:

| Field | Default | What it sets |
| --- | --- | --- |
| `migrations_connection` | `None` | the connection whose migrations write the messages table; `None` maps nothing |
| `table_name` | `messenger_messages` | the table mapped — the `table_name` the transports use |

Its zero-config path builds and boots with no application configuration and touches no database
until a transport runs a statement.

## Errors

Everything this library raises derives from `OrmMessengerError`, itself a
`MessageBusError` of [xtr-messenger](../xtr-messenger):

| Error | Raised when |
| --- | --- |
| `TransportError` | the database refuses what a transport asked — sending, claiming, settling, listing — or an envelope settled here was not received here; the driver's error is its cause |
| `InvalidOrmDsnError` | an `orm://` DSN names a connection the application does not configure; also a `LookupError` |

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-orm-messenger`; run the commands below from there. The `python-xtr-orm-messenger`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

Every test runs on SQLite files. The PostgreSQL suite under `tests/postgresql/` runs when
`XTR_TEST_POSTGRES_URL` names a database, as an asyncpg URL:

```sh
XTR_TEST_POSTGRES_URL=postgresql+asyncpg://user:password@127.0.0.1/test uv run pytest tests/postgresql
```

## License

MIT — see [LICENSE](LICENSE).
