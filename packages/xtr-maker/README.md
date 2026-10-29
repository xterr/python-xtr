<div align="center">

# xtr-maker

**Console commands that write application code for the xtr libraries.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Every message, schedule, webhook, entity, command or listener starts as the same few files: a
class in the right folder, its imports, its decorator, a handler beside it. The `make:*`
commands write those files — named and placed the way the rest of the application is, formatted
the way the linter wants, and refused rather than overwritten when one already exists.

They are development tools: install the package as a development dependency and list its bundle
for the `dev` environment. Nothing reaches production, and nothing is written until a maker runs.

## Install

```sh
uv add --dev xtr-maker
```

The makers write code for libraries, so each one is offered only when that library's bundle is
active. An extra installs the library beside the makers, for an application that has not got it
yet:

```sh
uv add --dev "xtr-maker[messenger,scheduler,webhook,orm,event-dispatcher]"
```

## The makers

| Command | Writes | Listed when this bundle is active |
| --- | --- | --- |
| [`make:message`](#makemessage) | A message and its handler | `messenger` |
| [`make:schedule`](#makeschedule) | The provider of a schedule | `scheduler` |
| [`make:webhook`](#makewebhook) | A webhook's parser, consumer and route | `webhook` |
| [`make:entity`](#makeentity) | An entity and its repository, or fields on one | `orm` |
| [`make:command`](#makecommand) | A console command class | — (the console bundle alone) |
| [`make:listener`](#makelistener) | A listener or a subscriber of one event | `event_dispatcher` |
| [`make:migration`](#makemigration) | A revision of what the tables changed | `orm` |

`list make` shows the ones an application has. A maker whose bundle is not active is not
registered at all: there is no command that tells you to install something.

## Where the code goes

Each class goes in the folder named after what it is, under the application package, one public
class per module:

| Folder | Module | Written by |
| --- | --- | --- |
| `entity/` | `<snake>.py` | `make:entity` |
| `repository/` | `<snake>_repository.py` | `make:entity` |
| `message/` | `<snake>.py` | `make:message` |
| `message_handler/` | `<snake>_handler.py` | `make:message` |
| `scheduler/` | `<snake>_schedule.py` | `make:schedule` |
| `webhook/` | `<snake>_request_parser.py` | `make:webhook` |
| `remote_event/` | `<snake>_webhook_consumer.py` | `make:webhook` |
| `config/packages/` | `webhook_<snake>.py` | `make:webhook` |
| `command/` | `<snake>_command.py` | `make:command` |
| `event_listener/` | `<snake>_listener.py` | `make:listener` |
| `event_subscriber/` | `<snake>_subscriber.py` | `make:listener` |

A name may carry a subpackage: `make:message ordering.PlaceOrder` writes
`message/ordering/place_order.py`. A folder with no `__init__.py` gets one declaring nothing, so
the module imports by its dotted name and the container's scan finds it.

## `make:message`

```
make:message [name] [--transport TRANSPORT] [--wire-name WIRE_NAME]
```

Writes `message/<snake>.py` — a frozen slotted dataclass declared with `@as_message` — and
`message_handler/<snake>_handler.py`, a class whose `async def __call__(self, message)` takes it.

| Asked | Answer | Default |
| --- | --- | --- |
| The message's class name | `PlaceOrder`, `"place order"`, `ordering.PlaceOrder` | none: it must be answered |
| The transport it goes to when no route names one | `[no transport]`, or one of `MessageBusConfig.transports` | `[no transport]` |
| The name it travels under | any non-empty text | `<package>.<snake>.v1` |

- The transport question is skipped when the bus has no transport configured; a `--transport`
  that names none is refused, listing the configured ones.
- The wire name is pinned in the decorator, so moving the class later changes nothing on the wire.
- With `-n`: the name must be on the command line, the transport is none unless `--transport`
  names one, and the wire name is its default.

```sh
$ uv run app make:message PlaceOrder --transport async -n
 created: src/app/message/place_order.py
 created: src/app/message_handler/place_order_handler.py

  [OK] Wrote PlaceOrder and PlaceOrderHandler.

Next:
  - Open src/app/message/place_order.py and add its fields.
  - Open src/app/message_handler/place_order_handler.py and write what handling it does.
```

## `make:schedule`

```
make:schedule [name] [--schedule SCHEDULE] [--message MESSAGE] [--stateful] [--lock]
```

Writes `scheduler/<snake>_schedule.py`: an `@as_schedule("<schedule>")` provider deriving from
`ScheduleProviderInterface`, which builds its `Schedule` once in its constructor.

| Asked | Answer | Default |
| --- | --- | --- |
| The provider's class name | `ReportSchedule`, `"report"` — `Schedule` is appended if missing | none: it must be answered |
| The schedule it provides | letters, digits, `_`, `-` or `.` | `default` |
| The message it sends every hour | `[empty schedule]`, or one of the application's `@as_message` classes | `[empty schedule]` |
| Keep what already ran in the scheduler cache pool? | yes/no, asked only with the `cache` bundle active | no |
| Send from the worker holding a lock only? | yes/no, asked only with the `lock` bundle active | no |

- The messages offered are the `@as_message` classes of the application package, by class name,
  or `module:Class` when two share one. A message whose constructor takes arguments is written as
  a comment instead, so the module imports and the kernel boots before its fields are known.
- A schedule another declared provider already provides is refused. One that only tasks are
  declared on is free: the tasks join this schedule.
- `--stateful` without the `cache` bundle, or `--lock` without the `lock` bundle, is refused,
  naming the bundle to activate.
- With `-n`: the name must be given, the schedule is `default`, and nothing is sent, kept or
  locked unless the options say so.

```sh
$ uv run app make:schedule ReportSchedule --schedule reports -n
 created: src/app/scheduler/report_schedule.py

  [OK] Wrote ReportSchedule, which provides the reports schedule.

Next:
  - Open src/app/scheduler/report_schedule.py and set what it sends, and how often.
  - Run it: messenger:consume scheduler_reports
```

## `make:webhook`

```
make:webhook [name] [--matcher MATCHER]...
```

The name is the webhook type: the last segment of the URL its sender posts to, and the source
name of the events it carries. Three modules come out of it:

| Module | Holds |
| --- | --- |
| `webhook/<snake>_request_parser.py` | An `AbstractRequestParser`: `get_request_matcher` claims the sender's requests, `do_parse` compares the signature header with the secret and reads a `RemoteEvent` from the JSON body |
| `remote_event/<snake>_webhook_consumer.py` | An `@as_remote_event_consumer("<type>")` class with `async def consume(self, event)` |
| `config/packages/webhook_<snake>.py` | A `@configure` transform adding a `RouteConfig(parser=..., secret=env("<TYPE>_WEBHOOK_SECRET"))` to whatever routing is configured |

The matchers are asked for one at a time — `[done]`, then every one not picked yet — whether or
not the name was given, each written with placeholder arguments to replace:

`Attributes`, `Callable`, `Header`, `Host`, `Ips`, `IsJson`, `Method`, `Path`, `Port`,
`QueryParameter`, `Scheme`.

- One matcher is returned as it is; several are wrapped in a `ChainRequestMatcher`; none writes
  an empty chain, with a comment saying it claims every request.
- `--matcher` takes a name with or without `RequestMatcher`, without case, repeatable; one that
  is not offered is refused, listing them.
- A type the webhook configuration already routes is refused. The routed types are read as the
  kernel builds, not from the injected configuration, so a secret that is not set yet does not
  stop the next webhook from being made.
- With `-n`: the name must be given, and the matchers are `Method` and `IsJson` unless
  `--matcher` names others.

```sh
$ uv run app make:webhook stripe --matcher Method -n
 created: src/app/webhook/stripe_request_parser.py
 created: src/app/remote_event/stripe_webhook_consumer.py
 created: src/app/config/packages/webhook_stripe.py

  [OK] Wrote StripeRequestParser, StripeWebhookConsumer and the stripe route.

Next:
  - Add STRIPE_WEBHOOK_SECRET to .env.local: the secret stripe shares with you.
  - Open src/app/webhook/stripe_request_parser.py and replace the secret check with the one its sender's protocol asks for.
  - Open src/app/remote_event/stripe_webhook_consumer.py and write what an event leads to.
  - Make sure config/routes/webhook.py exists, with an @as_routes function including resources["webhook"]: the sender posts to /webhook/stripe.
```

## `make:entity`

```
make:entity [name] [--field FIELD]... [--relation RELATION]... [--id uuid|uuid7|bigint] [--no-audit]
```

A new entity gets `entity/<snake>.py`, stored in the plural of its name, and
`repository/<snake>_repository.py` — a `SQLAlchemyAsyncRepository` subclass with an `@as_service`
factory scoped like the `AsyncSession` it takes. An entity that exists gets only the new
properties, every other line kept as it was, and no repository.

The base class comes from `--id` and `--no-audit`:

| `--id` | Audited (the default) | `--no-audit` |
| --- | --- | --- |
| `uuid` (the default) | `UUIDAuditBase` | `UUIDBase` |
| `uuid7` | `UUIDv7AuditBase` | `UUIDv7Base` |
| `bigint` | `BigIntAuditBase` | `BigIntBase` |

Both only choose a new entity's base; either one given for an entity that exists is refused.

**Fields** — `--field name:type[:settings][?]`, repeatable; `?` makes the column nullable, which
also makes the attribute `T | None`:

| Type | Attribute | Column |
| --- | --- | --- |
| `string[:length]` | `str` | `String(length)`, 255 by default |
| `text` | `str` | `Text` |
| `integer`, `big_integer`, `small_integer` | `int` | `Integer`, `BigInteger`, `SmallInteger` |
| `boolean` | `bool` | `Boolean` |
| `float` | `float` | `Float` |
| `decimal[:precision[:scale]]` | `Decimal` | `Numeric(precision, scale)`, `10, 2` by default |
| `date`, `time` | `date`, `time` | `Date`, `Time` |
| `datetime` | `datetime` | `DateTimeUTC(timezone=True)` |
| `json` | `dict[str, object]` | `JsonB` |
| `uuid` | `UUID` | `GUID` |
| `enum:<dotted class>` | the enum class | `Enum(<class>)` |
| `binary` | `bytes` | `LargeBinary` |

Asked for one at a time, the type offered is the one the name suggests — `_at` a `datetime`,
`_id` a `uuid`, `is_`/`has_` a `boolean`, anything else a `string` — and `?` at the prompt lists
them all.

**Relations** — `--relation name:kind:Target[?][,inverse=name|none]`, repeatable:

| Kind | This entity gets | The other entity gets |
| --- | --- | --- |
| `many_to_one` | `<name>_id` with a `ForeignKey`, and the `relationship` | a collection, named after this one in the plural |
| `one_to_many` | a collection | the key and the `relationship`; the inverse must be named |
| `one_to_one` | a unique `<name>_id` and the `relationship` | one of this entity |
| `many_to_many` | a collection through an association table, written in a module of its own | a collection |

`?` makes the foreign key nullable, which `many_to_many` has not got. `inverse=none` adds nothing
to the other entity; left out, the inverse is this entity's name, pluralized when that side
reaches many of it. The other entity is imported for annotations only: the relationship finds it
by name once every entity is mapped.

With `--field` or `--relation`, or with `-n`, nothing is asked. With neither and a terminal, the
questions run until a property name is left empty. Every name is checked before anything is
written: a property the entity already has, or an unimportable enum, leaves both entities as they
were.

```sh
$ uv run app make:entity Book --field title:string:120 -n
 created: src/app/entity/book.py
 created: src/app/repository/book_repository.py

  [OK] Wrote Book and BookRepository.

Next:
  - Run make:migration to write the revision the change needs.
  - Then run orm:migrations:migrate -n to apply it.
```

## `make:command`

```
make:command [name] [--argument ARGUMENT]... [--option OPTION]...
```

Writes `command/<snake>_command.py`: a class declared with `@as_command`, named after the last
part of the console name — `app:send-report` is `SendReportCommand`. Its `__call__` takes the
arguments, then the options after a bare `*`, each documented in the docstring `--help` reads,
and its body prints every value it was given, so the command runs as soon as it is written.

- `--argument name[?][:type]`: `?` makes it optional. Types are `str` (the default), `int`,
  `float`, `list` (`list[str]`) and an enum class as `module.Class`.
- `--option name[:type]`: types are `bool` (the default) and the same others.
- A list argument takes every value left, so none is asked after it; a required argument may not
  follow an optional one; `io` is reserved; names are unique.
- A name a command already answers to is refused, and so is one whose last part cannot name a
  class.
- With neither `--argument` nor `--option` and a terminal, they are asked one at a time until a
  name is left empty. With `-n` and neither, the command takes a `name` argument and a `yell`
  option to start from.

```sh
$ uv run app make:command app:send-report --argument recipient -n
 created: src/app/command/send_report_command.py

  [OK] Wrote SendReportCommand.

Next:
  - Run app:send-report --help to see its arguments and options.
  - Open src/app/command/send_report_command.py and write what it does.
```

## `make:listener`

```
make:listener [name] [event]
```

A name ending in `Listener` writes `event_listener/<snake>_listener.py`, a class whose
`async def on_<event>` method carries `@as_event_listener`. One ending in `Subscriber` writes
`event_subscriber/<snake>_subscriber.py`, deriving from `EventSubscriberInterface` and mapping the
event to that method in `get_subscribed_events`. Any other name is asked which, a listener by
default, and the suffix is appended.

The event is a class — by its name, as `module:Class`, or as a dotted path — or a name it is
dispatched under. When it is asked, the events found are listed: those of the installed xtr
packages, those of the application's own `event` package, and those the dispatcher already has a
listener for. A name close to some of them is answered with what it may have meant; a name that
matches none is offered as a plain dispatch name to confirm, and the generated code then imports
`Event` for the annotation.

With `-n` both the name and the event must be given, and the event must resolve: a plain dispatch
name needs the question, so it is refused.

```sh
$ uv run app make:listener WorkerStatsSubscriber WorkerStartedEvent -n
 created: src/app/event_subscriber/worker_stats_subscriber.py

  [OK] Wrote WorkerStatsSubscriber, reacting to xtr_messenger.event:WorkerStartedEvent.

Next:
  - Open src/app/event_subscriber/worker_stats_subscriber.py and write what on_worker_started_event does.
```

## `make:migration`

```
make:migration [--message MESSAGE] [--connection CONNECTION]
```

The only maker with no template of its own: it compares a connection's database with its table
definitions and lets the connection's migrator write the revision, into its migrations directory,
exactly as `orm:migrations:diff` does. The file is never opened or edited afterwards.

- `--message` names what the revision does, and its file; asked when left out, defaulting to
  `auto`. An empty one is refused.
- `--connection` picks the connection; the default one when left out. One the registry does not
  know is refused, listing the names it has.
- The database must have every revision applied first, or the comparison would see what is still
  to run rather than what the tables add. A database that is behind reports how many revisions are
  waiting, then `Run orm:migrations:migrate -n first.`
- Nothing differing is a note, `No database changes were detected.`, and a successful exit with
  nothing written.

```sh
$ uv run app make:migration --message books -n
 created: migrations/20261029105403_c51185006457_books.py

  [OK] Wrote the revision c51185006457.

Next:
  - Review the new revision, then run orm:migrations:migrate -n.
```

## What every maker does, and never does

- **Nothing is overwritten.** A target that exists, or one another file of the same run already
  claimed, ends the run before anything reaches the disk. The exception is `make:entity` on an
  entity that exists: it adds the new properties and their imports and writes the module back,
  every other line byte-identical.
- **All or nothing.** A run renders every file first and writes them together, so a name already
  taken or a template that renders source which does not parse leaves the working tree as it was.
- **Configuration is never edited.** `make:webhook` writes a new `@configure` transform module
  rather than touching the application's webhook configuration; every other maker writes no
  configuration at all.
- **Secrets are never generated.** A maker that needs one prints the `.env.local` step instead.
- **Nothing is written outside the project.** A path that leaves the project directory, or is a
  symbolic link, is refused, so what is typed at a prompt cannot reach elsewhere on disk.
- **Where the code goes** is `MakerConfig.root_package`, or, with none configured, the kernel's
  own name. Classes are marked `@final` unless `MakerConfig.final_classes` is off.
- **The application package is found when a maker first needs it** — `src/<package>/`, else
  `<package>/` at the project root — never when the console starts.

## Generated code and the linters

Every module is written the way the formatter would write it: 88-column lines, double quotes,
imports grouped standard library, third-party then the application's own package and sorted the
way the import rules sort them, a statement too long for one line wrapped with a trailing comma.
Each file opens with a docstring, `from __future__ import annotations` and its `__all__`.

Two things to know when the project's own settings are stricter:

- **Annotations read at runtime.** A console command's parameter types, and a container-hydrated
  constructor's, are read at runtime, so they cannot move into `if TYPE_CHECKING:`. `make:command`
  writes the `# noqa: TC001`, `TC002` or `TC003` — with the reason — on the imports that would
  otherwise be flagged. Everything genuinely used for annotations only is already in a
  `TYPE_CHECKING` block.
- **Two-way relations.** `make:entity` writes each side's import of the other under
  `TYPE_CHECKING`; basedpyright's `reportImportCycles` sees the pair as a cycle all the same. It
  is the shape SQLAlchemy relationships take: silence the rule for the entities, or keep the
  inverse out with `inverse=none`.

A project whose formatter runs at a different line length should simply run it over what was
written; nothing in the generated code depends on the width.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what removing
it undoes.

- **Install** — `uv add --dev xtr-maker`: the makers write code while you develop, so they are a
  development dependency, never a runtime one. Add the extras of the libraries you want makers
  for if the application has not got them yet.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below, and only that:
  it lists `MakerBundle` for the `dev` environment. There is nothing for it to configure, no
  variable to write and nothing to ignore, so it prints no step for you to make. Run it after
  `uv add --dev`: `recipes:add` installs a runtime dependency, which this is not.
- **Activate** — `MakerBundle: {"dev": True}` in `BUNDLES` in `<app>/config/bundles.py`, imported
  from `xtr_maker.bundle`.
- **Brings along** — the console bundle, which the makers are commands of. The messenger,
  scheduler, webhook, orm and event dispatcher bundles are not brought along: each is read, not
  required, and decides which makers are registered.
- **Configure** — optional: with no configuration the code goes into the kernel's own package and
  every class is `@final`.

  ```python
  # <app>/config/packages/maker.py
  from xtr_dependency_injection import configure
  from xtr_maker.bundle import MakerConfig


  @configure
  def maker() -> MakerConfig:
      return MakerConfig(root_package="acme.shop", final_classes=True)
  ```

- **Environment** — nothing. A maker that needs a secret prints the variable to set in
  `.env.local` rather than reading one itself.
- **Ignore** — nothing: what the makers write is code to commit.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/packages/maker.py` if you wrote
  one, then `uv remove --dev xtr-maker`. The code the makers wrote stays yours.
- **Check** — `debug:bundles` lists `maker` as active in `dev`; `list make` shows one `make:*`
  command for each library whose bundle is active.

## Kernel / bundle

`MakerBundle` is declared `@as_bundle("maker", config=MakerConfig)` and requires the console
bundle. Its `load_extension` registers three services and then the command module of each maker
whose library's bundle is active:

| Service | Lifetime | Is |
| --- | --- | --- |
| `TemplateRenderer` | singleton | The templates this package ships, rendered, then parsed before anything is queued |
| `FileManager` | singleton | The project directory and the application package, and the only way a maker writes |
| `Generator` | scoped | One maker run's queue of files: a failed run leaves nothing queued for the next |

`MakerConfig` is a frozen dataclass buildable with no arguments:

| Field | Default | Is |
| --- | --- | --- |
| `root_package` | `None` | The dotted application package the makers write into; `None` takes the kernel's name. A value that is not a dotted Python identifier raises `InvalidArgumentError` |
| `final_classes` | `True` | Whether generated classes are marked `@final` |

## Errors

All of them derive from `MakerError`, so one `except` catches anything that can stop a maker:

| Error | Raised when |
| --- | --- |
| `AppPackageNotFoundError` | The application package is neither under `src/` nor at the project root |
| `GeneratedSourceError` | A template rendered Python that does not parse; it names the template |
| `InvalidArgumentError` | An argument, option or answer cannot be used — also a `ValueError` |
| `InvalidClassNameError` | What was typed cannot name a class: a keyword, no identifier, or shadowing a builtin |
| `TargetExistsError` | A file to write exists, or another file of the same run already claimed it — also a `FileExistsError` |
| `UnsafePathError` | A path leaves the project directory, or is a symbolic link |

A command turns them into an exit code rather than a traceback: `ExitCode.INVALID` for anything
refused before the files are rendered, `ExitCode.FAILURE` for a target that exists or a migration
that could not be written, `ExitCode.SUCCESS` otherwise — nothing to write included.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-maker`; run the commands below from there. The `python-xtr-maker`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
