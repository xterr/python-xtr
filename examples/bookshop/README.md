# bookshop — a complete application on the xtr packages

One kernel, three entry points (a console, a web application, a message worker), every
bundle, and every decorator the packages ship — a schedule, a cache, locks and events
included. It is written to be read: each module says
what it demonstrates and why, and every behaviour below was observed by running it.

It is its own uv project, **not** a member of the repository's workspace: every `xtr-*`
package comes from `../../packages`, editable, so a change there is visible here at once.

```sh
cd examples/bookshop
uv sync
uv run bookshop list                  # the console
uv run bookshop-web                   # http://127.0.0.1:8080 — Ctrl-C to stop
uv run python -m bookshop.worker jobs # a worker (in dev the queues are in-memory: returns at once)
uv run bookshop messenger:consume scheduler_default -vv   # the schedule — Ctrl-C to stop
```

The environment comes from the `.env` cascade (`APP_ENV=dev` by default). A real variable
always wins: `APP_ENV=prod uv run bookshop di:show`, `APP_ENV=test uv run bookshop list`.

## A tour in commands

| Command | Shows |
|---|---|
| `bookshop list [namespace]` | every command, grouped by namespace; hidden ones left out |
| `bookshop debug:bundles` | which bundles are active and why — listed, required, skipped |
| `bookshop debug:config [bundle]` | each config's resolution steps; placeholders shown as `env(NAME)` |
| `bookshop debug:container [--tag TAG]` | every definition, in emission order |
| `bookshop debug:router` · `router:match PATH [--method M]` | the web application's routes, and which one a path reaches — the application is only read, nothing is served |
| `bookshop di:show [-v] [--report scan]` | removals, decorations, collection order, parameters, the compiler log |
| `bookshop env:show` | every env processor's result, and the typed settings |
| `bookshop catalog:list [--genre software] [-l 2] [--output csv\|json\|markdown]` | options, `Literal`, `Enum`, a validator, a `ServiceLocator` |
| `bookshop catalog:price ISBN [QTY]` | the ordered `Sequence[PricingRule]`; the quote cached five minutes in the `quotes` pool — run it twice |
| `bookshop catalog:add ISBN TITLE PRICE [--author A] [-y]` | a class command, questions |
| `bookshop orders:place ISBN [QTY] [--email E] [--no-drain] -vv` | scoped and transient services, the bus, fan-out, a worker, logs following `-vv`; a lock per book, an `OrderPlaced` event and the tally its subscriber keeps, a handler's result, a declared stamp read back after the serialized `jobs` transport (`-vvv`) |
| `bookshop orders:reindex [REASON] [--via outbox]` | a pydantic message, `TransportNamesStamp` |
| `bookshop search:query WORDS [-s]` · `search:stats` | commands a library's bundle contributes, loaded late |
| `bookshop cache:clear` · `logs:recent` | `ServicesResetter`; a configured handler reached by name |
| `bookshop cache:pool:list` · `cache:pool:clear quotes` · `cache:pool:prune` | the cache bundle's commands: `app`, `quotes`, and the `scheduler` pool the scheduler bundle adds |
| `bookshop debug:scheduler [--sort] [--all] [--date D]` | the schedule and its tasks with their next runs — from the saved checkpoint once it has run |
| `bookshop messenger:consume scheduler_default --time-limit 7 -vv` | the schedule, run: a heartbeat every two seconds in dev, each run's result; start it again and it resumes; start two and only one sends |
| `bookshop demo:errors` | every guided error of every package, caught and printed |
| `bookshop demo:style --end raise` (hidden) | every `ConsoleStyle` method and every way a run ends |
| `bookshop dotenv:dump` · `debug:dotenv [NAME]` | the dotenv bundle's commands |
| `bookshop bundle:check` · `demo:frozen-clock` · `demo:wireup` · `demo:dotenv` · `demo:without-container` | dev and test only — the `dev_tools` bundle |

## The web application

`uv run bookshop-web` serves `bookshop.web.app:app` on `WEB_HOST` / `WEB_PORT` — the routes of
`web/routes.py`, written the way the framework documents them, with the container behind the
same markers a command uses. `uv run fastapi dev src/bookshop/web/app.py` serves the very same
application with reloading and `/docs`, once the framework's `standard` extra is installed.

```sh
curl -i localhost:8080/health          # every response carries an X-Request-Id
curl 'localhost:8080/books?genre=history'
curl 'localhost:8080/books/978-0135957059?quantity=5'
curl 'localhost:8080/search?q=pride'
curl localhost:8080/orders
curl -i -X POST localhost:8080/orders -H 'content-type: application/json' \
  -d '{"isbn":"978-0141439518","quantity":2,"email":"ada@example.com"}'   # 201
curl -i localhost:8080/books/nope       # 404 {"error": "no book with ISBN nope"}
```

An unknown ISBN and a refused order are raised as the domain errors they are; `web/app.py`
gives each a status — 404 and 422 — with one exception handler apiece. Without the server:
`bookshop debug:router` lists every route in the order routing tries them, and
`bookshop router:match /books/978-0135957059` names the one a path reaches and what it reads
out of it — neither needs `--app`, because `config/http_kernel.py` names the application.

## Layout

```
examples/bookshop/
├── .env .env.dev .env.test .env.prod .env.local .env.dev.local   the cascade
├── resources/            files env processors read; dotenv-demo/ holds only a .env.dist
├── secrets/              one file per variable, read by SecretsDirectoryLoader
├── var/                  logs, written at runtime (ignored)
└── src/
    ├── fulltext/         a reusable library shipping its own bundle — the library-author side
    └── bookshop/         the application
        ├── kernel.py     the Kernel recipe, the scan exclusions, load_environment()
        ├── bundles.py    the root bundles, per environment
        ├── config/       one @configure module per bundle, plus @parameters
        ├── scheduling/   the schedule, its tasks, and who hears about each run
        ├── __main__.py   console entry · web/ the web application · worker.py worker entry
        └── …             one package per concern, below
```

## Where each feature lives

### Kernel and bundles

| Feature | File |
|---|---|
| `Kernel(package, name=, allowed_envs=, exclude=)`; env and debug from `APP_ENV` / `APP_DEBUG` | `bookshop/kernel.py` |
| `kernel.run(console)` · `setup(app, kernel)` — build, lifespan and request scopes in one call · `kernel.boot()` | `__main__.py` · `web/app.py` · `worker.py` |
| `Kernel(environ=)`, `kernel.with_env()`, `engine_container()` | `dev_tools/commands.py`, `commands/demo_errors.py` |
| `BUNDLES` with `{"all": True}` and `{"dev": True, "test": True}` | `bookshop/bundles.py` |
| A bundle with every hook: `build`, `prepend_extension`, `load_extension`, `process`, `boot`, `shutdown` | `fulltext/bundle/fulltext_bundle.py` |
| `@as_bundle(name, config=, resources=)`; `@required_bundle` by class, by `"module:Class"`, `ignore_on_invalid` | `fulltext/bundle/fulltext_bundle.py`, `dev_tools/dev_tools_bundle.py` |
| A bundle whose only job is `resources`, with `NoConfig` | `dev_tools/dev_tools_bundle.py` |
| `register_attribute_for_autoconfiguration` reading a library's own decorator | `fulltext/decorator/as_analyzer.py` + the bundle's `build` |
| `register_for_autoconfiguration(T).add_tag(...)`, `add_compiler_pass(stage=, priority=)`, `set_parameter`, `bundle_active` | `fulltext/bundle/fulltext_bundle.py` |
| `prepend_extension_config(LoggingConfig, …)` with `LoggingConfig.with_channels` | `fulltext/bundle/fulltext_bundle.py` |
| `services.set / instance / alias / load`, `.set_argument`, `.add_tag("kernel.reset", method=)`, `.set_decorated_service` | `fulltext/bundle/fulltext_bundle.py` |
| `builder.get_extension_config`, `find_tagged_service_ids`, `get_definition`, `log` | `fulltext/bundle/analyzer_pipeline_pass.py` |
| `ServiceLocator` inside a factory | `fulltext/bundle/fulltext_bundle.py`, `reporting/export_registry.py` |
| `AliasOf` — a config field forwarded to another bundle | `fulltext/bundle/fulltext_config.py`, `config/fulltext.py`, `config/clock.py` |
| `assert_zero_config` · `boot_for_test(overrides=)` | `dev_tools/commands.py` |
| `integration.wireup`: `create_container`, `injectables`, `engine_container` | `dev_tools/commands.py` |

### Every decorator of `xtr_dependency_injection`

| Decorator | File |
|---|---|
| `@as_service` bare, on a factory, `lifetime="scoped"` (a generator), `"transient"`, `qualifier=` | `catalog/in_memory_book_catalog.py`, `ordering/unit_of_work.py`, `ordering/order_number.py`, `notifications/notifiers.py`, `observability/logging_services.py` |
| `@as_alias(T)`, `@as_alias(T, qualifier=)` | `notifications/notifiers.py`, `observability/logging_services.py` |
| `@as_tagged_item(index=, priority=, before=, after=)` + `@as_alias(Base, qualifier=)` → an ordered `Sequence[Base]` / `Mapping[Hashable, Base]` | `pricing/rules.py`, `pricing/price_calculator.py` |
| `@as_tagged_item(before=, after=)` on class keys → emission order, read back from the report | `health/checks.py`, followed by `lifecycle.run_startup_checks` |
| `@autoconfigure(tags=[(name, callable)])`, `(lifetime=)`, `(factory=)` | `health/startup_check.py`, `ordering/request_scoped.py`, `reporting/exporters.py` |
| `@autoconfigure_tag(name, **attrs)`, repeated, and without a name | `pricing/pricing_rule.py` |
| `@as_decorator(T, priority=)` stacked; `qualifier=`; `OnInvalid.IGNORE`; `OnInvalid.NULL` | `catalog/catalog_decorators.py`, `notifications/notifiers.py`, `payments/payment_gateway.py`, `payments/fraud_check.py` |
| `@remove_if_missing(service=, qualifier=)`, `(class_=)`, `(package=)`, repeated | `observability/security_audit_trail.py`, `notifications/notifiers.py`, `catalog/redis_catalog_warmer.py`, `payments/payment_gateway.py` |
| `@when(...)`, `@when_not(...)`, `@when` repeated | `notifications/notifiers.py`, `payments/payment_gateway.py`, `lifecycle.py`, `config/*.py` |
| `@exclude` | `kernel.py`, `messaging/outbox_transport.py` |
| `@on_boot`, `@on_boot(priority=)`, `@on_shutdown(priority=)` | `lifecycle.py` |
| `@compiler_pass`, `(stage=, priority=)` at `BEFORE_OPTIMIZATION`, `OPTIMIZE`, `AFTER_REMOVING` | `compiler_passes.py` |
| `@configure` base, transform, `(priority=)`, under `@when` | `config/*.py` |
| `@parameters`; `%param%`, `%%`, `"%env(int:X)%"`; `env()` in every spelling | `config/parameters.py` |
| `Injected[T]`, `Autowire(param=)`, `Autowire(env=)`, `Target(q)`, `AutowireDecorated` | throughout; `env/env_showcase.py` for `env=` |
| `EnvVarProcessorInterface` · `EnvVarLoaderInterface` | `env/rot13_processor.py` · `env/secrets_directory_loader.py` |
| `ContainerInterface`, `ContainerBagInterface`, `KernelInterface`, `ServicesResetter`, `bind_callable` | `commands/showcase_commands.py`, `lifecycle.py` |
| The markers as the web framework's own dependencies, in a route signature | `web/routes.py` |

### The other packages

| Package | Feature | File |
|---|---|---|
| console | `@as_command` bare, named, `aliases=`, `description=`, `hidden=`; function and class commands; sync and async | `commands/*.py`, `fulltext/command/` |
| console | `Argument(...)`, `Option(alias=, count=, negative=, name=, env_var=, validator=)`, `Range`, `escape` | `commands/catalog_commands.py`, `commands/order_commands.py`, `commands/style_commands.py` |
| console | every `ConsoleStyle` method, questions, verbosity, exit codes | `commands/style_commands.py` |
| console | `Application.on_configure / on_startup / on_shutdown`, from a boot hook | `lifecycle.py` |
| console | `Application`, `CommandsLocator`, `CommandTester`, `ApplicationTester` without a kernel | `dev_tools/commands.py` |
| messenger | `@as_message` in every form; dataclass and pydantic messages | `messaging/messages.py` |
| messenger | `@as_message_handler` on functions and classes, `Envelope`, several handlers per message | `messaging/handlers.py` |
| messenger | `@as_middleware`, repeated; a middleware instance in the config; custom stamps | `messaging/middleware.py`, `messaging/stamps.py` |
| messenger | every `MessageBusConfig` / `TransportConfig` field; `sync://`, `in-memory://`; AMQP in prod | `config/messenger.py` |
| messenger | an application transport factory, found by the bundle | `messaging/outbox_transport.py` |
| logging | every handler, processor and formatter spec; capture (dev) and a stdlib handler (prod) | `config/logging.py` |
| logging | service ids for a handler, formatter, processor and activation strategy | `observability/logging_services.py` |
| logging | `@as_processor(channel=, handler=, priority=)` on classes and on a function | `observability/processors.py` |
| logging | `bound_context`, context vars; `Logger` / `LoggerFactory` without a kernel | `dev_tools/commands.py` |
| messenger | `@as_stamp` — a stamp of its own restored after a serializing transport | `messaging/stamps.py`, `messaging/handlers.py` |
| messenger | a handler's return value, on its `HandledStamp` | `messaging/handlers.py`, `commands/order_commands.py` |
| messenger | worker events — started, stopped, a message failed — heard by listeners | `scheduling/listeners.py` |
| messenger | `RedispatchMessage` — a scheduled message sent on through routing | `scheduling/shop_schedule.py` |
| messenger | a receiver registered as a service (`scheduler_<name>`, by the scheduler bundle), consumable with no transport configured | `config/messenger.py` names none |
| scheduler | `@as_schedule` — the README's starter schedule: `stateful` on the `scheduler` pool, a lock, `process_only_last_missed_run`, a schedule-local `before` listener | `scheduling/shop_schedule.py` |
| scheduler | `RecurringMessage.cron` hashed (`#hourly`), `.every(...).with_jitter`, a message of its own with a result | `scheduling/shop_schedule.py`, `scheduling/messages.py`, `scheduling/handlers.py` |
| scheduler | `@as_periodic_task` / `@as_cron_task` on a function, a class (`method=`), methods, with `arguments=`, `jitter=`, `env=`, `transports=` | `scheduling/tasks.py` |
| scheduler | `PostRunEvent`, `FailureEvent` heard application-wide | `scheduling/listeners.py` |
| scheduler | `SchedulerConfig` | `config/scheduler.py` |
| http-kernel | `setup(app, kernel)` — one kernel per application life, one scope per request | `web/app.py` |
| http-kernel | `HttpKernelConfig(app=)`, read by `debug:router` and `router:match` | `config/http_kernel.py` |
| http-kernel | the request lifecycle listed as a bundle: `X-Request-Id`, an uncaught exception on the `request` channel | `bundles.py` |
| event-dispatcher | a domain event (`Event`), `EventDispatcherInterface` injected, `@as_event_listener(priority=)`, an `EventSubscriberInterface` | `ordering/order_placed.py`, `ordering/order_service.py`, `ordering/order_listeners.py` |
| lock | a qualified `LockFactory` (`Target("stock")`), `async with lock` | `ordering/order_service.py`, `config/lock.py` |
| lock | the default `LockFactory`, a lock kept between runs | `scheduling/shop_schedule.py` |
| cache | `CacheConfig` with a pool of its own, `@when("test")` in memory | `config/cache.py` |
| cache | a qualified `CacheInterface`, fetch-or-compute with a callback | `commands/catalog_commands.py` |
| clock | `ClockInterface` injected, `Clock`, `MockClock`, `MonotonicClock`, `mock_time`, `DatePoint`, `ClockAwareMixin` | `ordering/order_number.py`, `fulltext/bundle/timed_search_engine.py`, `dev_tools/commands.py` |
| dotenv | `Dotenv().boot_env()` at the entry point; `parse / load / overload / populate / load_env` | `kernel.py`, `dev_tools/commands.py` |
| dotenv | `DotenvSettings` — typed settings from the same cascade | `settings.py` |
| service-contracts | `ResetInterface` (nominal) and an explicit `kernel.reset` tag | `catalog/catalog_decorators.py`, `fulltext/query_log.py` |

## Environment variables

`.env` documents every variable, one per env processor; `env:show` prints them resolved. The
packages themselves read or write:

| Variable | Read / written by |
|---|---|
| `APP_ENV` | the kernel's environment (`dev`, `test`, `prod` here) and the dotenv cascade |
| `APP_DEBUG` | the kernel's debug flag; `boot_env` writes `1` / `0` |
| `SHELL_VERBOSITY` | the console's starting verbosity, `-2` to `3`; `-q` / `-v` win |
| `XTR_DOTENV_VARS`, `XTR_DOTENV_PATH` | written by the dotenv loader |

The application reads `SHOP_*`, `SEARCH_*`, `DATABASE_URL`, `APP_TIMEZONE`, `WEB_HOST`,
`WEB_PORT`, and in prod `MESSENGER_TRANSPORT_DSN`, `MAILER_DSN`, `SHOP_PAYMENT_API_KEY`.
`SHOP_VAULT_TOKEN` is set nowhere on purpose: the secrets-directory loader supplies it.

## Rules this example follows

- **Never import what a package uses internally.** No `cyclopts`, `rich` or `msgspec` in
  application code; `wireup` only in `demo:wireup`, through `integration.wireup`, which exists
  for plain-wireup applications. Tune command parameters with `Argument` / `Option`, escape
  with `xtr_console.escape`, add a logging channel with `LoggingConfig.with_channels`.
- **Every string in a bundle config is parameter-resolved.** A literal `%` is written `%%`:
  `date_format="%%Y-%%m-%%d"` (`config/logging.py`).
- **`env()` is a placeholder while the kernel builds, never a value.** It cannot decide what
  the container contains (`if env(...)` raises); give a number a `default=` so config
  validation sees something plausible.
- **A command's, handler's or route's container parameters carry a marker** — `Injected[T]`,
  `Target(q)` for a qualified service, `Autowire(param=)`, `Autowire(env=)`. A bare `T` is a
  command-line argument, an HTTP parameter in a route, or refused in a handler. `Target`
  beside `Autowire(param=/env=)` is refused: a parameter is one of the three.
- **A sync hook cannot receive a service built asynchronously** — any logger, the console
  `Application`. Make the hook `async`.
- **Scoped and transient services exist only inside a scope** — a command run, a request (one
  is opened around every one of them), a handler call. `container.get()` refuses them, and a
  singleton cannot depend on them, so they are passed as arguments (`OrderService.place`).
- **Gate a class with `@when`, not its alias**: `@as_alias` is unconditional.
- **`exclude=` replaces `DEFAULT_EXCLUDES`**; extend it (`kernel.py`).
- **The dotenv bundle loads nothing**: `load_environment()` runs before the kernel is built.
- **A config another bundle forwards to with `AliasOf` takes no application base provider** —
  that is a `ConflictingConfigProvidersError`; transform it instead (`config/clock.py`).
- **A validator also sees a parameter's default** — except `None`, the default of an optional
  left out.

## Deliberate escape hatches

- `io.console` / `io.error_console` return rich's consoles, on purpose: they are the escape
  hatch for anything the style's methods do not draw. Using them makes rich the
  application's own choice; this example does not.
