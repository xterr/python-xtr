<div align="center">

# xtr-logging

**Channels, handlers, processors and formatters for Python — behind one logger interface.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="core dependencies: 5" src="https://img.shields.io/badge/core%20deps-5-3FB950">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Code that logs should depend on one small interface, not on how logging is set up. Where records
go — a file, syslog, standard error, nowhere unless something failed — is configuration.

What you get:

- 🧩 **One `LoggerInterface`** — eight severities plus `log()`, with a context mapping. A
  library takes one and defaults to `NullLogger`.
- 📡 **Channels** — one logger per concern (`app`, `security`, `db`), sharing handlers.
- 🫧 **Handlers bubble** — a stack consulted in order; a record stops where a handler keeps it.
- 🤞 **Fingers crossed** — buffer a request's whole log, and write it only if something failed.
- 🔧 **Processors** — enrich every record: placeholders, request ids, hostnames, call sites,
  ambient context.
- 📋 **Configuration as data** — channels, handlers and processors, readable from TOML or JSON.
- 🔁 **Standard library bridge** — third-party `logging` output flows into your channels, and
  yours can flow out.
- 🕰️ **An injectable clock** — record times come from [xtr-clock](https://github.com/xterr/python-xtr-clock),
  so a test freezes them.
- 🤝 **A contract a library can depend on alone** — the interface lives in
  [xtr-logging-contracts](https://github.com/xterr/python-xtr-logging-contracts), which has one
  dependency, so a library that only logs never installs any of this.
- 🪶 **Five core dependencies** — `msgspec`, `typing-extensions`, `xtr-clock`,
  `xtr-logging-contracts` and `xtr-service-contracts`.

```python
logger.error("payment {order} failed", {"order": order.id, "exception": error})
```

## Install

```sh
uv add xtr-logging              # everything but the container integration
uv add "xtr-logging[di]"        # + a logger per channel from an xtr-dependency-injection kernel
```

Requires Python 3.11+.

## Quick start

```python
from xtr_logging import Logger, PlaceholderProcessor, StreamHandler
from xtr_logging_contracts import Level

logger = Logger(
    "app",
    handlers=[StreamHandler("var/log/app.log", Level.INFO)],
    processors=[PlaceholderProcessor()],
)

logger.info("user {user} logged in", {"user": "ana"})
# [2026-09-24T12:30:45.123456+03:00] app.INFO: user ana logged in {"user":"ana"} []
```

Code that only *uses* a logger asks for the interface:

```python
from xtr_logging_contracts import LoggerInterface, NullLogger


class Checkout:
    def __init__(self, logger: LoggerInterface | None = None) -> None:
        self._logger = logger or NullLogger()
```

## The logger interface

The interface, `Level`, `Context`, `NullLogger`, `AbstractLogger` and `LoggerAware` belong to
[xtr-logging-contracts](https://github.com/xterr/python-xtr-logging-contracts) and are imported
from there, not from here. This package exports only what it owns — loggers, handlers,
processors, formatters and configuration — so there is exactly one place each name comes from and
no chance of two packages disagreeing about what `LoggerInterface` is.

So a library that only logs depends on `xtr-logging-contracts` at runtime and keeps `xtr-logging`
as a dev dependency for its tests; an application depends on both and wires them together.

```python
class LoggerInterface(Protocol):
    def emergency(self, message: str, /, context: Context | None = None) -> None: ...
    def alert(self, message: str, /, context: Context | None = None) -> None: ...
    def critical(self, message: str, /, context: Context | None = None) -> None: ...
    def error(self, message: str, /, context: Context | None = None) -> None: ...
    def warning(self, message: str, /, context: Context | None = None) -> None: ...
    def notice(self, message: str, /, context: Context | None = None) -> None: ...
    def info(self, message: str, /, context: Context | None = None) -> None: ...
    def debug(self, message: str, /, context: Context | None = None) -> None: ...
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None: ...
```

The rules:

- `context` is a mapping of anything. Formatters describe what they cannot serialise; a value
  never makes logging fail.
- An exception to report goes under `context["exception"]`. Formatters print its class, message,
  origin and cause, and the traceback if asked.
- `{key}` placeholders in the message are filled from context by `PlaceholderProcessor`, not by
  the logger, so a handler can still see the template and the values apart.

`AbstractLogger` implements the eight methods on top of `log()`, so an implementation writes one
method. With the `LoggerAware` mixin a class gets a `logger` that is a `NullLogger` until
`set_logger()` is called.

> ruff's `PLE1205` assumes every `logger.info(...)` is the standard library's and flags the
> context mapping as a stray format argument. Ignore it in projects using this interface.

### Levels

The eight RFC 5424 severities, valued so they compare as integers:

| Level | Value | RFC 5424 | | Level | Value | RFC 5424 |
| --- | --- | --- | --- | --- | --- | --- |
| `DEBUG` | 100 | 7 | | `ERROR` | 400 | 3 |
| `INFO` | 200 | 6 | | `CRITICAL` | 500 | 2 |
| `NOTICE` | 250 | 5 | | `ALERT` | 550 | 1 |
| `WARNING` | 300 | 4 | | `EMERGENCY` | 600 | 0 |

Anywhere a level is accepted, `Level.parse` reads it: a `Level`, its value, an RFC 5424 severity,
or a name in any case (`"error"`). Anything else raises `InvalidLevelError`.

## Records, handlers and bubbling

Each call becomes an immutable `LogRecord`: `datetime`, `channel`, `level`, `message`, `context`,
and `extra` (what processors added, kept apart so a processor never overwrites the caller).

A logger offers the record to its handlers in stack order. A handler handles records at its
`level` or above; with `bubble=False` a record it handled goes no further:

```python
logger = Logger(
    "app",
    [
        StreamHandler("var/log/errors.log", Level.ERROR, bubble=False),  # errors stop here
        StreamHandler("var/log/app.log"),  # everything else
    ],
)
```

`push_handler()` puts a handler on top, `pop_handler()` takes it off. `with_name("security")`
returns a logger for another channel that shares these handlers.

A handler or processor that raises propagates to the caller. Pass
`exception_handler=` to a `Logger` to receive such failures instead, or wrap handlers in a
`WhatFailureGroupHandler`. A handler that logs while handling a record is stopped three levels
deep, with a warning, rather than recursing until the stack overflows.

### Handlers

| Handler | Does |
| --- | --- |
| `StreamHandler` | Writes to a stream or a file, opened on first write, parent directories created |
| `RotatingFileHandler` | One file per day (or any `date_format`), keeping the newest `max_files` |
| `SyslogHandler` | Syslog over UDP or a socket such as `/dev/log`, with the right severity |
| `ConsoleHandler` | Standard error, or any stream set later, its level following `-v` verbosity, coloured on a terminal |
| `NullHandler` | Swallows records at its level |
| `TestHandler` | Keeps records in memory for assertions |
| `FingersCrossedHandler` | Buffers everything; writes it all once one record is bad enough |
| `BufferHandler` | Buffers records and writes them as a batch on `close()` |
| `GroupHandler` | Sends every record to every member |
| `WhatFailureGroupHandler` | A group where a failing member never stops the others |
| `FallbackGroupHandler` | Tries members in order until one succeeds |
| `FilterHandler` | Passes a level range, or a list of levels, to the handler it wraps |
| `DeduplicationHandler` | Drops an error already written in the last `time` seconds |
| `SamplingHandler` | Passes one record in `factor` |
| `QueueHandler` | Writes on a background thread, so logging never waits on I/O |
| `StdlibHandler` | Hands records to a standard-library logger |

### Fingers crossed

The handler to run in production. Records are buffered; nothing is written until one
reaches the action level, and then the whole buffer is — so a failed request leaves its full
story, and a healthy one leaves nothing:

```python
from xtr_logging import FingersCrossedHandler, Logger, StreamHandler
from xtr_logging_contracts import Level

logger = Logger("app", [FingersCrossedHandler(StreamHandler("var/log/app.log"), Level.ERROR)])
```

`ChannelLevelActivationStrategy` sets a different trigger per channel, `buffer_size` caps the
buffer, and `passthru_level` keeps records at that level even when nothing triggered. Call
`reset()` between the requests or messages of a long-running process so one unit of work does not
bleed into the next.

## Processors

A processor is any callable `(LogRecord) -> LogRecord`. Logger processors run once per record,
and only once some handler will handle it:

| Processor | Adds |
| --- | --- |
| `PlaceholderProcessor` | Fills `{placeholders}` in the message from context |
| `ContextVarsProcessor` | Whatever is bound with `bind_context()` / `bound_context()` |
| `UidProcessor` | A random id shared by every record until `reset()` |
| `IntrospectionProcessor` | The file, line, function and module that logged |
| `HostnameProcessor`, `ProcessIdProcessor` | The machine, the process |
| `TagProcessor` | A fixed list of tags |

Ambient context rides along without being passed to every call. It lives in a context variable,
so it is separate per thread and per asyncio or anyio task:

```python
from xtr_logging import bound_context

with bound_context({"request_id": request.id, "user": user.id}):
    handle(request)  # every record logged in here carries both
```

Declare a processor where it is written, and a factory attaches it:

```python
from xtr_logging import LogRecord, as_processor


@as_processor(channel="billing")
def add_tenant(record: LogRecord) -> LogRecord:
    return record.with_extra({"tenant": current_tenant()})
```

`channel=` limits a processor to one channel. `handler=` attaches it to a handler instead;
handlers are shared, so it then applies on every channel that handler serves. Higher `priority`
runs first.

## Formatters

| Formatter | Renders |
| --- | --- |
| `LineFormatter` | `[%datetime%] %channel%.%level_name%: %message% %context% %extra%` |
| `JsonFormatter` | One JSON object per record, or a batch as an array or as lines |
| `ConsoleFormatter` | A short line with the level coloured |

`LineFormatter` also knows `%level%` and `%context.KEY%` / `%extra.KEY%` for one entry. It keeps
each record on one line unless `allow_inline_line_breaks` is set, and prints tracebacks when
`include_stacktraces` is set. `Normalizer`, which both formatters build on, reduces any value to
plain data, cutting nesting and collections short at a limit.

## Configuration

A `LoggingConfig` describes channels, handlers and processors as data. It builds nothing; a
`LoggerFactory` does:

```python
from xtr_logging import LoggerFactory, LoggingConfig
from xtr_logging.config import (
    ConsoleHandlerSpec,
    FingersCrossedHandlerSpec,
    PlaceholderProcessorSpec,
    StreamHandlerSpec,
)

CONFIG = LoggingConfig(
    channels=("security", "billing"),
    handlers={
        "main": FingersCrossedHandlerSpec(action_level="error", handler="file"),
        "file": StreamHandlerSpec(path="var/log/prod.log"),
        "console": ConsoleHandlerSpec(channels=("!event",)),
    },
    processors=(PlaceholderProcessorSpec(),),
)

factory = LoggerFactory(CONFIG)
security = factory.logger("security")
```

Or read it from a file, TOML here:

```toml
channels = ["security"]

[handlers.main]
type = "fingers_crossed"
action_level = "error"
handler = "file"

[handlers.file]
type = "stream"
path = "var/log/prod.log"
formatter = { type = "json" }

[handlers.audit]
type = "rotating_file"
path = "var/log/audit.log"
max_files = 30
channels = ["security"]
level = "notice"

[[processors]]
type = "placeholder"
```

```python
config = LoggingConfig.from_mapping(tomllib.loads(Path("logging.toml").read_text()))
```

The rules:

- **Channels.** `app` (`default_channel`) always exists. `channels` adds more, and a channel
  named in any handler's `channels` is declared too. Asking for any other channel raises
  `UnknownChannelError`. `config.with_channels("mail")` returns a copy declaring more — what a
  bundle calls from `prepend_extension` to give itself a channel.
- **Channel filters.** `channels: "security"` or `["a", "b"]` includes; `"!event"` or
  `["!a", "!b"]` excludes. Mixing the two raises `MixedChannelFilterError`. A filter applies only
  to a handler on a channel's stack, not to one nested in another handler.
- **Nesting.** A wrapper names what it wraps (`handler: file`, `members: [a, b]`). A handler
  named that way, or marked `nested`, is left off every channel's stack.
- **Priority.** Higher is consulted first; ties keep declaration order.
- **Services.** `type: service` names an object you supply, as do a formatter given by name and
  an `activation_strategy`:

  ```python
  LoggerFactory(CONFIG, services=Services(handlers={"sentry": SentryHandler(dsn)}))
  ```

Everything is checked as the configuration is made. A typo'd key, a level that does not exist or
a value of the wrong type raises `InvalidConfigurationError` naming the path. A wrapper naming a
missing handler raises `UnknownHandlerError`, and wrappers nesting each other in a loop raise
`CircularHandlerReferenceError`.

Handler types: `stream`, `rotating_file`, `syslog`, `console`, `null`, `stdlib`, `service`,
`fingers_crossed`, `buffer`, `filter`, `deduplication`, `sampling`, `queue`, `group`,
`whatfailuregroup`, `fallbackgroup`. Processor types: `placeholder`, `context_vars`, `uid`,
`introspection`, `hostname`, `process_id`, `tags`, `service`.

The factory builds every handler once, as it is made, and shares each between channels. Files
open on first write. `reset()` ends a unit of work. `close()` writes whatever is buffered or
queued; use the factory as a context manager, or close it on shutdown. `set_verbosity()` sets
every console handler at once, from command-line flags:

```python
factory.set_verbosity(Verbosity.from_count(args.verbose, quiet=args.quiet, silent=args.silent))
```

The map: `--silent` prints nothing, `-q`
errors and up, no flag warnings and up, `-v` notices, `-vv` info, `-vvv` everything.
`set_console_stream(stream, colors=...)` points every console handler at another stream — a
command's error output — with colours forced on or off. [xtr-console](https://github.com/xterr/python-xtr-console)
does both for every command it runs when its container provides the factory.

## The standard library

Libraries you depend on — httpx, SQLAlchemy, uvicorn — log through `logging`. Left alone, their
records go wherever `logging` is set up to send them, and none of your channels see them. A
`capture` section brings them in:

```toml
channels = ["db"]

[capture]
level = "warning"          # the threshold for every stdlib logger not listed below

[capture.loggers]
httpx = "info"             # a level of its own; httpx._client and every child follow it
"sqlalchemy.engine" = { level = "warning", channel = "db" }   # and a channel of its own
```

Captured records become records on a channel — `app` unless `channel` or a logger's entry says
otherwise — and go through its processors and handlers like any other: fingers-crossed, JSON,
files. `extra=` values become context, `exc_info` becomes `context["exception"]`, and the
original time is kept. A logger's entry covers its children; the most specific name wins.

**Nothing is written twice.** Capture does not add a handler next to the ones already there; it
takes the standard library's output over:

- every existing stdlib handler is moved aside — a root `StreamHandler` from `basicConfig`, one
  a library put on its own logger — and every logger propagates to the root, where one capture
  handler is the only output;
- a handler attached while capture is on — by `addHandler`, `basicConfig` or `dictConfig` — is
  held aside rather than attached, and the capture's own handler cannot be removed;
- a record with nowhere else to go, from a logger reconfigured not to propagate, is captured
  instead of printed raw by `logging.lastResort`.

The factory installs the capture as it is built and gives everything back — handlers, levels,
flags, `Logger.addHandler` itself — on `close()`. A `stdlib` handler, which sends records into
`logging`, cannot be combined with a capture: its records would come straight back and be lost,
so the configuration refuses it with `CaptureConflictError`.

Without a factory, `StdlibCapture` does the same, as a context manager or with `install()` and
`release()`:

```python
from xtr_logging.bridge.stdlib import StdlibCapture

with StdlibCapture(logger, levels={"httpx": "info"}, routes={"sqlalchemy": db_logger}):
    serve()
```

The other way round, `StdlibHandler` hands records to a stdlib logger, keeping their time,
channel and context. `StdlibLogger` puts the interface in front of a plain `logging.Logger` for
code that keeps `logging` as its backend.

## Kernel / bundle

An application using [xtr-dependency-injection](../xtr-dependency-injection) lists
`LoggingBundle` in its `app/bundles.py` and configures it with `@configure`. A service asks
for the default channel by the interface, and for any other by qualifying it with the
channel's name:

```sh
uv add "xtr-logging[di]"
```

```python
# app/bundles.py
from xtr_logging.bundle import LoggingBundle

BUNDLES = {LoggingBundle: {"all": True}}
```

```python
# app/config/logging.py
from xtr_dependency_injection import as_service, configure

from xtr_logging import TestHandler
from xtr_logging.bundle import LoggingConfig
from xtr_logging.config import ServiceHandlerSpec
from xtr_logging.handler.handler_interface import HandlerInterface


@configure
def logging() -> LoggingConfig:
    return LoggingConfig(
        channels=("security",),
        handlers={"main": ServiceHandlerSpec(id="main")},
    )


@as_service(qualifier="main")
def main_handler() -> HandlerInterface:
    return TestHandler()
```

```python
# anywhere in the app
from typing import Annotated

from xtr_dependency_injection import Target, as_service
from xtr_logging_contracts import LoggerInterface


@as_service
class Checkout:
    def __init__(
        self,
        logger: LoggerInterface,
        audit: Annotated[LoggerInterface, Target("security")],
    ) -> None: ...
```

The bundle registers the `LoggerFactory`, a `LoggerInterface` for the default channel, and a
`LoggerInterface` qualified by each channel's name. `LoggerFactory` inherits `ResetInterface`,
so the kernel's `ServicesResetter` resets it between messages. A `ServiceHandlerSpec`,
`ServiceProcessorSpec`, a string `formatter` and a fingers-crossed `activation_strategy` name
services the application registers under `HandlerInterface`, `ProcessorInterface`,
`FormatterInterface` or `ActivationStrategyInterface` with `qualifier=id`; a missing id fails
the build with `UnknownServiceError` naming the id.

A class decorated `@as_processor` — with the kernel scanning the module — becomes a service
(its constructor injected) and the bundle attaches its instance to every logger it builds; a
decorated function is the processor itself and is attached as it is. `channel=`, `handler=`
and `priority=` apply to both, and both stay instantly usable outside a kernel too.
`@required_bundle("xtr_clock.bundle:ClockBundle", ignore_on_invalid=True)` pulls in the clock
bundle when installed, so records read the same instant as an injected clock.

## Time

Every record is stamped by an [xtr-clock](https://github.com/xterr/python-xtr-clock)
`ClockInterface`. Pass one as `clock=` to a `Logger`, a `LoggerFactory` or a
`DeduplicationHandler`; without one they read whichever clock is in force, so a test freezes
every record's time without touching the logger:

```python
from xtr_clock import Clock, MockClock

with Clock.using(MockClock("2026-09-24 12:00:00")):
    logger.info("frozen")  # stamped 2026-09-24 12:00:00+00:00
```

Records captured from the standard library keep their original time, in the local zone like a
native record.

## Testing your application

`TestHandler` keeps what it handles:

```python
from xtr_logging import Logger, TestHandler
from xtr_logging_contracts import Level

handler = TestHandler()
checkout = Checkout(Logger("app", [handler]))

checkout.pay(order)

assert handler.has_record_that_contains("payment", Level.ERROR)
```

It also answers `has_records(level)`, `has_record(message, level, context)`,
`has_record_that_matches(pattern, level)` and `has_record_that_passes(predicate, level)`, and
keeps the rendered text in `formatted`. With a factory, configure a `service` handler and pass a
`TestHandler`, or fetch any configured handler with `factory.handler(name)`.

## Errors

Everything the library raises derives from `LoggingError` and carries typed attributes.

| Error | Raised when |
| --- | --- |
| `InvalidLevelError` | A value names no level (also a `ValueError`) |
| `InvalidOptionError` | An option has a value its handler or processor cannot use |
| `EmptyStackError` | A handler or processor is popped from an empty stack |
| `InvalidConfigurationError` | Configuration data does not fit, with the path to what is wrong |
| `MixedChannelFilterError` | A channel list mixes `foo` and `!foo` |
| `UnknownChannelError` | A logger or processor names a channel that is not declared |
| `UnknownHandlerError` | A wrapper, processor or lookup names a handler that is not defined |
| `CircularHandlerReferenceError` | Wrappers nest each other in a loop |
| `UnknownServiceError` | Configuration names a service that was not supplied |
| `NotProcessableHandlerError` | A processor targets a handler that runs none |
| `CaptureConflictError` | A `stdlib` handler is configured while capture is on |

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-logging`; run the commands below from there. The `python-xtr-logging` repository is a
read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check . && uv run ruff format --check .
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
