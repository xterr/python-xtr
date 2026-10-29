---
name: xtr-maker
description: Generate application code for the xtr libraries with the make:* console commands of xtr-maker - messages and handlers, schedule providers, webhook parsers and consumers, entities and repositories, console commands, event listeners and subscribers, and migration revisions. Use when scaffolding any of those by hand, when asking which folder a generated class belongs in, when scripting a maker non-interactively with -n, when a maker is missing from `list make`, when a run is refused with TargetExistsError or InvalidClassNameError, when deciding what make:entity's --field and --relation accept, or when adding MakerBundle to an application on xtr-dependency-injection.
---

# xtr-maker

Dev-only console commands that write code: a class in the folder named after what it is, its
imports, its decorator, and whatever belongs beside it. Nothing is overwritten, nothing is
written outside the project, and no secret is ever generated.

## Quick reference

| Command | Writes | Needs this bundle active |
| --- | --- | --- |
| `make:message [name] [--transport T] [--wire-name N]` | `message/<snake>.py`, `message_handler/<snake>_handler.py` | `messenger` |
| `make:schedule [name] [--schedule S] [--message M] [--stateful] [--lock]` | `scheduler/<snake>_schedule.py` | `scheduler` |
| `make:webhook [name] [--matcher M]...` | `webhook/<snake>_request_parser.py`, `remote_event/<snake>_webhook_consumer.py`, `config/packages/webhook_<snake>.py` | `webhook` |
| `make:entity [name] [--field F]... [--relation R]... [--id uuid\|uuid7\|bigint] [--no-audit]` | `entity/<snake>.py`, `repository/<snake>_repository.py` | `orm` |
| `make:command [name] [--argument A]... [--option O]...` | `command/<snake>_command.py` | — |
| `make:listener [name] [event]` | `event_listener/<snake>_listener.py` or `event_subscriber/<snake>_subscriber.py` | `event_dispatcher` |
| `make:migration [--message M] [--connection C]` | a revision in the connection's migrations directory | `orm` |

- Anything left off the command line is asked; `-n` asks nothing and takes the defaults, but the
  name always has to be given.
- A name may carry a subpackage: `ordering.PlaceOrder` lands in `message/ordering/place_order.py`.
- A run renders every file before it writes any, so a refusal leaves the working tree untouched.
- `list make` shows what the application has. A maker whose library's bundle is not active is not
  registered.

## A message and its handler

```sh
uv run app make:message PlaceOrder --transport async -n
```

Writes a frozen slotted dataclass under `@as_message(name="app.place_order.v1",
transport="async")` and a handler class whose `async def __call__(self, message)` takes it. The
transport is one of `MessageBusConfig.transports`; the wire name defaults to
`<package>.<snake>.v1` and is pinned, so moving the class later changes nothing on the wire.

## A schedule

```sh
uv run app make:schedule ReportSchedule --schedule reports --message RestockCheck -n
```

Writes an `@as_schedule("reports")` provider sending `RestockCheck()` every hour. `--stateful`
needs the `cache` bundle active, `--lock` the `lock` bundle. A schedule another declared provider
provides is refused. Then: `messenger:consume scheduler_reports`.

## A webhook

```sh
uv run app make:webhook stripe --matcher Method --matcher IsJson -n
```

Writes the parser, the consumer and `config/packages/webhook_stripe.py` — a `@configure`
transform adding `RouteConfig(parser=..., secret=env("STRIPE_WEBHOOK_SECRET"))`. Matchers are
`Attributes`, `Callable`, `Header`, `Host`, `Ips`, `IsJson`, `Method`, `Path`, `Port`,
`QueryParameter`, `Scheme`; several are chained. Set `STRIPE_WEBHOOK_SECRET` in `.env.local`
yourself, and make sure `config/routes/webhook.py` exposes `resources["webhook"]`.

## An entity

```sh
uv run app make:entity Book \
  --field title:string:120 --field published_at:datetime? \
  --relation author:many_to_one:Author,inverse=books -n
```

New: the entity on `UUIDAuditBase` (`--id uuid7|bigint`, `--no-audit` pick another base) in the
plural of its name, plus its repository. Existing: only the new properties are added, every other
line byte-identical, and no repository — `--id` and `--no-audit` are then refused. Field types:
`string`, `text`, `integer`, `big_integer`, `small_integer`, `boolean`, `float`, `decimal`,
`date`, `datetime`, `time`, `json`, `uuid`, `enum:<dotted class>`, `binary`; `?` makes a column
nullable. Relation kinds: `many_to_one`, `one_to_many`, `many_to_many`, `one_to_one`;
`inverse=none` adds nothing to the other entity. Then run `make:migration`.

## A console command

```sh
uv run app make:command app:send-report --argument recipient --option dry-run -n
```

`app:send-report` becomes `SendReportCommand`. Argument types are `str`, `int`, `float`, `list`
and a dotted enum class; options add `bool`, which is their default. A list argument must be last,
a required argument may not follow an optional one, and `io` is reserved.

## A listener or a subscriber

```sh
uv run app make:listener WorkerStatsSubscriber WorkerStartedEvent -n
```

A name ending in `Subscriber` writes an `EventSubscriberInterface` with
`get_subscribed_events`; one ending in `Listener` writes a class whose `on_<event>` method carries
`@as_event_listener`. The event is a class name, `module:Class` or a dotted path. With `-n` it has
to resolve to a class: a plain dispatch name needs the confirmation question, so it is refused.

## A migration

```sh
uv run app make:migration --message books -n
```

Compares the connection's database with its table definitions and lets its migrator write the
revision, as `orm:migrations:diff` does. Every revision must be applied first, or the run fails
with `Run orm:migrations:migrate -n first.` Nothing differing writes nothing and still succeeds.

## Testing

- Generated code is ordinary application code: test it the way the application tests the rest.
  Nothing of xtr-maker is imported at runtime by what it writes.
- To script a maker inside a test or a setup script, pass `-n` and every value as an option: with
  no terminal nothing is asked, so the run never blocks.
- Templates are rendered and then parsed, so a template that produces broken Python fails loudly
  with `GeneratedSourceError` rather than writing a file.
- Run the project's own gate over what was written; it is formatted (split statements keep a
  trailing comma, so any line length from 88 up accepts them) with sorted imports, so it passes
  unchanged. It assumes `TC001`/`TC002`/`TC003` are off: command parameters, constructor
  parameters and entity columns are annotations read at runtime. A two-way relation's entities
  carry `# pyright: reportImportCycles=false` above their `TYPE_CHECKING` imports of each other.

## Use in an application

1. **Install** — `uv run xtr-recipes recipes:add --dev xtr-maker` (or `uv add --dev xtr-maker`,
   then `uv run xtr-recipes recipes:sync`). Add extras for libraries the application has not got
   yet: `"xtr-maker[messenger,scheduler,webhook,orm,event-dispatcher]"`.
2. **Recipe** — the recipe shipped here does step 3 and nothing else; it lists the bundle for
   `dev`.
3. **Activate** — `from xtr_maker.bundle import MakerBundle` at the top of
   `<app>/config/bundles.py`, and `MakerBundle: {"dev": True}` in `BUNDLES`, which the recipe
   writes. Production without the development dependencies still starts: the kernel stands in for
   the bundle there, which is not active, and never needs its package.
4. **Brings along** — the console bundle. The messenger, scheduler, webhook, orm and event
   dispatcher bundles are read, never required: each decides which makers exist.
5. **Configure** — nothing to configure: the code goes into `kernel.package`, found where the
   import system loads it, and classes are `@final`. To change either, write the settings into
   the `dev` environment folder — production does not install this package, and only a `dev`
   build imports that folder:

   ```python
   # <app>/config/packages/dev/maker.py (beside an empty __init__.py)
   from xtr_dependency_injection import configure
   from xtr_maker.bundle import MakerConfig


   @configure
   def maker() -> MakerConfig:
       return MakerConfig(final_classes=False)
   ```

6. **Environment** — nothing. A maker that needs a secret prints the variable to set.
7. **Ignore** — nothing: what the makers write is code to commit.
8. **Remove** — `uv run xtr-recipes recipes:remove xtr-maker`: `uv remove --dev xtr-maker`, then a
   sync that drops the `BUNDLES` entry. Delete `<app>/config/packages/dev/maker.py` if you wrote
   one. The generated code stays yours.
9. **Check** — `debug:bundles` lists `maker` as active in `dev`; `list make` shows the makers.

## Errors

Every one derives from `MakerError`, in `xtr_maker.exception`:

| Error | Raised when |
| --- | --- |
| `AppPackageNotFoundError` | The import system finds no package of that name; the message names `MakerConfig.root_package` |
| `GeneratedSourceError` | A template rendered Python that does not parse; it names the template |
| `InvalidArgumentError` | An argument, option or answer cannot be used — also a `ValueError` |
| `InvalidClassNameError` | What was typed is no identifier, is a keyword, or would hide a builtin |
| `TargetExistsError` | The file exists, or another file of the same run claimed it — also a `FileExistsError` |
| `UnsafePathError` | A path leaves the project directory, or is a symbolic link |

A maker reports them and returns an exit code rather than a traceback: `ExitCode.INVALID` for
anything refused before the files are rendered, `ExitCode.FAILURE` for a target that exists or a
revision that could not be written, `ExitCode.SUCCESS` otherwise — nothing to write included.

## Do not

- Do not install it as a runtime dependency, and do not list `MakerBundle` for `all`: the makers
  belong in `dev`.
- Do not put a `MakerConfig` in a module directly under `<app>/config/packages/`: every
  environment imports those, and production, which does not install `xtr-maker`, fails to start.
  Use `<app>/config/packages/dev/`.
- Do not expect a maker to overwrite a file, or to edit configuration. `make:webhook` adds a
  transform module; `make:entity` is the only maker that writes an existing file, and only to add
  properties to it.
- Do not wait for a maker to generate a secret or run a migration: it prints the step.
- Do not hand-place a generated class elsewhere and expect the next maker to find it — the
  folders in the table above are where the makers look.
- Do not run a maker in `-n` mode and leave the name off; it is the one thing never defaulted.
- Do not run `make:migration` on a database behind its revisions; apply them first.
