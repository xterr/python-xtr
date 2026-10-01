# bookshop — a complete application on the xtr packages

One kernel, three entry points (a console, a web application, a message worker), every
bundle, and every decorator the packages ship — a schedule, a cache, locks, events and a
database included. It is written to be read: each module says
what it demonstrates and why, and every behaviour below was observed by running it.

It is its own uv project, **not** a member of the repository's workspace: every `xtr-*`
package comes from `../../packages`, editable, so a change there is visible here at once.

```sh
cd examples/bookshop
uv sync
uv run bookshop orm:migrations:migrate -n   # once: the orders and receipts tables
uv run bookshop jwt:generate-keypair --kid jwt-private-key --output-dir secrets   # once: the JWT signing key
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
| `bookshop orders:place ISBN [QTY] [--email E] [--no-drain] -vv` | scoped and transient services, the bus, fan-out, a worker, logs following `-vv`; a lock per book, an `OrderPlaced` event and the tally its subscriber keeps, a handler's result, a declared stamp read back after the serialized `jobs` transport (`-vvv`); one database transaction per message, its follow-ups sent once it committed |
| `bookshop orders:place 978-0141439518 13` | a handler refusing after it wrote the order row: `orm_transaction` rolls the row back, the receipt it asked for is never sent, the command reports `rolled back` and exits 1 |
| `bookshop orders:list` | the orders in the database, newest first, with their receipts — two per order, one written by each transport `SendReceipt` fans out to |
| `bookshop orders:reindex [REASON] [--via outbox]` | a pydantic message, `TransportNamesStamp` |
| `bookshop search:query WORDS [-s]` · `search:stats` | commands a library's bundle contributes, loaded late |
| `bookshop cache:clear` · `logs:recent` | `ServicesResetter`; a configured handler reached by name |
| `bookshop cache:pool:list` · `cache:pool:clear quotes` · `cache:pool:prune` | the cache bundle's commands: `app`, `quotes`, and the `scheduler` pool the scheduler bundle adds |
| `bookshop debug:scheduler [--sort] [--all] [--date D]` | the schedule and its tasks with their next runs — from the saved checkpoint once it has run |
| `bookshop messenger:consume scheduler_default --time-limit 7 -vv` | the schedule, run: a heartbeat every two seconds in dev, each run's result; start it again and it resumes; start two and only one sends |
| `bookshop demo:errors` | every guided error of every package, caught and printed |
| `bookshop demo:style --end raise` (hidden) | every `ConsoleStyle` method and every way a run ends |
| `bookshop dotenv:dump` · `debug:dotenv [NAME]` | the dotenv bundle's commands |
| `bookshop orm:migrations:status` · `migrate -n` · `up-to-date` · `diff "MESSAGE"` | where the database stands; bring it to the latest revision; exit 1 while one is not applied; write a revision from what the models changed |
| `bookshop orm:run-sql "select count(*) from orders"` | a statement run on the connection, its rows as a table |
| `bookshop debug:firewall [name]` | the firewalls the security bundle built, or one described |
| `bookshop debug:bundles` | now lists `security` (required by jwt) and `jwt` (listed) active |
| `bookshop jwt:check-config` | signs a probe token with the configured key and reads it back |
| `bookshop security:hash-password [PASSWORD] [USER-CLASS] [--empty-salt]` | hashes a password with the configured factory — the hashes `config/security.py` stores |
| `bookshop jwt:generate-keypair` · `jwt:generate-token IDENTIFIER` | mint a signing key, or a token for a user |
| `bookshop bundle:check` · `demo:frozen-clock` · `demo:wireup` · `demo:dotenv` · `demo:without-container` | dev and test only — the `dev_tools` bundle |
| `bookshop demo:rate-limit` | dev and test only — every limiter of `config/rate_limiter.py` under a frozen clock, then every limited route served in process; each row a claim checked, exit 1 if one fails |
| `bookshop demo:security` | dev and test only — the firewall, the roles and the `ORDER_VIEW` voter served in process: 401 without a token, 200 with one, 403 on a role or an owner denial; each row a claim checked, exit 1 if one fails |

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

`GET /orders` reads the database through the request's repository; `POST /orders` with 13
copies answers 409 `{"error": "rolled back", ...}`, and the order is not in the next
`GET /orders`.

Every route is rate limited, each the way it suits (`web/routes.py`, limiters in
`config/rate_limiter.py`):

```sh
curl -i localhost:8080/books            # X-RateLimit-Limit: 120 — the router's limit, per client
for i in 1 2 3 4 5 6; do curl -s -o /dev/null -w '%{http_code} ' 'localhost:8080/search?q=a'; done
                                        # 200 200 200 200 200 429 — a decorator, five a minute
curl -i 'localhost:8080/search?q=a'     # 429 {"error": "too many requests", "limiter": "search", ...}
                                        #     with Retry-After
```

- the router carries `api` — every route, 120 a minute per client, reported in
  `X-RateLimit-*`; `/books/1` and `/books/2` share one count, the route's template being the key;
- `GET /search` is decorated with `search` — five a minute, counted in this process only;
- `POST /orders` lists `ordering` in its `dependencies` — a burst of three per client, and at
  most a thousand a calendar month for the whole shop — and consumes `orders_per_email` by hand,
  injected by name, since the address is in the body: a third order from one address in an
  hour is 429 `{"error": "too many orders from this address"}`, raised by `ensure_accepted()`;
- a refusal is answered in the shop's own shape by two exception handlers in `web/app.py`, and
  written to the `security` channel by `observability/rate_limit_audit.py`, which hears the
  `RateLimitExceededEvent` every refusing route dispatches.

Limits are not only for routes: `send_receipt` (`messaging/handlers.py`) reserves a slot of the
mail provider's ten a minute (`outbound_mail`) and waits for it — or, past half a minute, raises
so the worker retries the message later.

An unknown ISBN, an order the fraud check refused and one a handler refused are raised as the
errors they are; `web/app.py` gives each a status — 404, 422 and 409 — with one exception
handler apiece. A handler failing for any other reason is a fault, not a refusal: it is raised
on, and answered 500. Without the server:
`bookshop debug:router` lists every route in the order routing tries them, and
`bookshop router:match /books/978-0135957059` names the one a path reaches and what it reads
out of it — neither needs `--app`, because `config/http_kernel.py` names the application.

### Security — a firewall, roles and a voter

One `api` firewall (`config/security.py`) covers every route and accepts a self-issued JSON Web
Token; the JWT bundle (`config/jwt.py`) signs with the key minted once into `secrets/` (see the start). The
catalog, search, the order list and placing an order stay open — the shop has always served them
so — while a single order, `/me` and the admin slice require a caller, and `/admin` an admin:

```sh
curl -i localhost:8080/me                       # 401 — WWW-Authenticate: Bearer
TOKEN=$(curl -s -X POST localhost:8080/token \
  -H 'content-type: application/json' \
  -d '{"identifier":"ada@example.com","password":"s3cret"}' | jq -r .access_token)
curl -s -H "Authorization: Bearer $TOKEN" localhost:8080/me          # {"identifier":"ada@example.com","roles":["ROLE_USER"]}
curl -i -H "Authorization: Bearer $TOKEN" localhost:8080/admin/stats # 403 — ada is not an admin
ADMIN=$(curl -s -X POST localhost:8080/token \
  -H 'content-type: application/json' \
  -d '{"identifier":"root@example.com","password":"r00t"}' | jq -r .access_token)
curl -s -H "Authorization: Bearer $ADMIN" localhost:8080/admin/stats # 200 {"orders": N}
```

- `web/routes.py` puts `Firewall()` on the router, so every route authenticates once and is
  checked against the access-control map; `/token` verifies the password with
  `UserPasswordHasherInterface` (a dummy hash burned for an unknown identifier, so the timing
  gives nothing away), then signs a token with `JwtTokenManagerInterface`, throttled by the
  `orders_per_email` limiter;
- `/me` injects the caller with `CurrentUser()`; `/admin/stats` carries `@IsGranted("ROLE_ADMIN")`,
  granted to `root@example.com` and, through the role hierarchy (`ROLE_ADMIN` reaches `ROLE_USER`),
  to nothing less;
- `GET /orders/{number}` is a customer's own order: `ordering/order_voter.py`'s `OrderViewVoter`
  grants `ORDER_VIEW` to the user whose identifier is the order's `email`, checked in the body
  with `Security.deny_access_unless_granted` — another customer is answered 403;
- the three inline users (`ada@example.com`, `lin@example.com`, `root@example.com`) and their
  argon2id password hashes are in `config/security.py`; `security:hash-password` prints a hash
  of the same shape, and `jwt:check-config` proves the signing key signs and verifies.

`demo:security` runs this whole loop in process (`httpx.ASGITransport`, like `demo:rate-limit`)
and checks every outcome.

> **Known gap.** `IsGranted(attribute, subject=<callable>)` does not work in a served route:
> the security-http package builds the subject dependency under `from __future__ import
> annotations`, so FastAPI reads the synthetic parameter's `Depends(...)` as an unresolved
> forward reference and treats it as a query parameter (a `422`). `IsGranted(attribute)` and
> `IsGranted(attribute, subject="path_param")` are unaffected; the owner check uses the
> `Security` facade in the body instead, the form the plan documents.

## Layout

```
examples/bookshop/
├── .env .env.dev .env.test .env.prod .env.local .env.dev.local   the cascade
├── resources/            files env processors read; dotenv-demo/ holds only a .env.dist
├── secrets/              one file per variable (SecretsDirectoryLoader) + the minted JWT key (ignored)
├── migrations/           the database's revisions, written by orm:migrations:diff
├── var/                  logs and the dev / test SQLite files, written at runtime (ignored)
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

The `.env.local`, `.env.dev.local` and `.env.prod` files and `secrets/SHOP_VAULT_TOKEN` are
committed on purpose, so the example runs as cloned: their values are placeholders. The JWT
signing key is the exception — a private key never enters the repository, so it is minted once
with `jwt:generate-keypair` into `secrets/`, which `.gitignore` keeps out. In an application of
your own, ignore the `.local` files too, and keep every secret out of the repository.

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
| messenger | `DispatchAfterCurrentBusStamp` — follow-ups held back until the message that asked for them committed | `messaging/handlers.py` |
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
| http-kernel | `RateLimited` on a router, as a decorator, in a route's `dependencies`; `TooManyRequestsError` reshaped by an exception handler | `web/routes.py`, `web/app.py` |
| rate-limiter | every policy — `sliding_window`, `fixed_window` (and on a calendar, `anchor_at`), `token_bucket`, `compound` with a shared key; in-memory, cache-pool and (prod) Redis storage | `config/rate_limiter.py`, `.env.prod` |
| rate-limiter | a limiter injected by name (`Target`), `consume()` and `ensure_accepted()` in a route, `reserve(max_time=)` and `wait()` in a handler | `web/routes.py`, `messaging/handlers.py` |
| rate-limiter | `RateLimitExceededEvent` heard by a listener; `RateLimiterBuilder`; `reset()`; every limit checked under `mock_time` | `observability/rate_limit_audit.py`, `dev_tools/rate_limit_demo.py` |
| event-dispatcher | a domain event (`Event`), `EventDispatcherInterface` injected, `@as_event_listener(priority=)`, an `EventSubscriberInterface` | `ordering/order_placed.py`, `ordering/order_service.py`, `ordering/order_listeners.py` |
| lock | a qualified `LockFactory` (`Target("stock")`), `async with lock` | `ordering/order_service.py`, `config/lock.py` |
| lock | the default `LockFactory`, a lock kept between runs | `scheduling/shop_schedule.py` |
| cache | `CacheConfig` with a pool of its own, `@when("test")` in memory | `config/cache.py` |
| cache | a qualified `CacheInterface`, fetch-or-compute with a callback | `commands/catalog_commands.py` |
| clock | `ClockInterface` injected, `Clock`, `MockClock`, `MonotonicClock`, `mock_time`, `DatePoint`, `ClockAwareMixin` | `ordering/order_number.py`, `fulltext/bundle/timed_search_engine.py`, `dev_tools/commands.py` |
| dotenv | `Dotenv().boot_env()` at the entry point; `parse / load / overload / populate / load_env` | `kernel.py`, `dev_tools/commands.py` |
| dotenv | `DotenvSettings` — typed settings from the same cascade | `settings.py` |
| service-contracts | `ResetInterface` (nominal) and an explicit `kernel.reset` tag | `catalog/catalog_decorators.py`, `fulltext/query_log.py` |
| orm | `OrmConfig` with one connection: the URL from `env("resolve:...")`, engine and session options, migrations under the project | `config/orm.py` |
| orm | engine and session options in the URL's query — `pool_pre_ping`, `expire_on_commit`, `pool_size` — taking precedence over the config | `.env`, `.env.prod` |
| orm | advanced-alchemy models, and repositories as scoped services on the unit of work's session | `ordering/order.py`, `ordering/receipt.py`, `ordering/order_repository.py`, `ordering/receipt_repository.py` |
| orm | `orm_close_connection`, `orm_transaction`, `orm_open_transaction_logger` with named arguments, in the order they need | `config/messenger.py` |
| orm | handlers sharing a message's session, a refusal rolling back what they wrote, the transport a receipt came through | `messaging/handlers.py` |
| orm | a command and a route reading through repositories; a rolled-back message reported | `commands/order_commands.py`, `web/routes.py`, `web/app.py` |
| orm | a generated revision | `migrations/` |
| security | `SecurityConfig` — inline users, `password_hashers`, `role_hierarchy`, one firewall, `access_control` | `config/security.py` |
| security | `Firewall()` on a router; `CurrentUser()`; `@IsGranted("ROLE_ADMIN")`; `Security.deny_access_unless_granted` in a body | `web/routes.py` |
| security | a `Voter` subclass granting `ORDER_VIEW` to an order's owner, gathered by the `security.voter` tag | `ordering/order_voter.py` |
| security | `UserPasswordHasherInterface` verifying a password, with a dummy-hash timing guard | `web/routes.py` |
| security | `debug:firewall`, `security:hash-password` (the `console` extra) | the bundle registers them |
| jwt | `JwtConfig` — the signing key from `env("resolve:...")`, `token_ttl`, `user_id_claim` | `config/jwt.py` |
| jwt | `JwtAuthenticatorConfig()` in a firewall; `JwtTokenManagerInterface.create(user)` in `/token` | `config/security.py`, `web/routes.py` |
| jwt | `jwt:generate-keypair`, `jwt:generate-token`, `jwt:check-config` (the `console` extra) | the bundle registers them |

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
`WEB_PORT`, and in prod `MESSENGER_TRANSPORT_DSN`, `MAILER_DSN`, `SHOP_PAYMENT_API_KEY`,
`SHOP_RATE_LIMIT_STORAGE` (a Redis DSN for the `orders` limiter; `cache` when unset).
`SHOP_DATABASE_URL` is the database — a SQLite file per environment in dev and test,
PostgreSQL in prod; `DATABASE_URL` only shows the env processors.
`SHOP_VAULT_TOKEN` is set nowhere on purpose: the secrets-directory loader supplies it.
`JWT_SECRET_KEY_PATH` points `config/jwt.py` at the PEM that signs self-issued tokens — the
key `jwt:generate-keypair` minted under `secrets/`; `config/jwt.py` reads it with `env("resolve:...")` so
`%kernel.project_dir%` expands, and the JWT bundle's key loader reads the file.

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
- **A handler never commits.** Under `orm_transaction` the message's handlers commit together
  once all of them succeeded; a handler's own `commit()` would end that transaction early.
  Everything the application writes goes through a message, so `orders:list` and
  `GET /orders` only read.
- **A follow-up waits for the commit.** What a handler dispatches to a transport is sent at
  once unless stamped `DispatchAfterCurrentBusStamp`; stamped, a worker never sees a receipt
  for an order not committed yet, and an order rolled back sends nothing.
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
