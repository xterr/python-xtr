---
name: xtr-logging
description: How to log through one interface and decide elsewhere where records go, with xtr-logging and xtr-logging-contracts. Use when code needs a logger, a channel per concern (app, security, db), handlers that write to a file, syslog, standard error or nowhere unless a request failed, fingers-crossed buffering, processors that add request ids or placeholders, JSON or line formatting, capturing third-party `logging` output, asserting on log records in a test, or adding LoggingBundle to an application on xtr-dependency-injection.
---

# xtr-logging

Logging is two halves. Code that logs takes a `LoggerInterface` from
`xtr-logging-contracts` and calls it; where the records go — a file, syslog, nowhere unless
something failed — is configuration the application owns, in `xtr-logging`. Keep the halves
apart and a library never installs handlers it does not use.

## Quick reference

- Type every parameter and attribute as `LoggerInterface`, imported from
  `xtr_logging_contracts`. `xtr-logging` does not re-export it.
- Pass values as context, never as f-strings: `logger.info("user {user} logged in", {"user": id})`.
- Report a failure with `context[EXCEPTION_KEY]`, not a formatted traceback.
- Make logging optional for callers: `logger or NullLogger()`.
- Build one logger by hand: `Logger("app", handlers, processors)`. Build many from data:
  `LoggerFactory(LoggingConfig(...))`.
- Ambient values for a whole block: `with bound_context({"request_id": rid}):` plus a
  `ContextVarsProcessor`.
- Tests: `TestHandler()` and its `has_record_*` questions. Freeze record times with
  `Clock.using(MockClock(...))`.
- In an application: activate `LoggingBundle`, inject `LoggerInterface` for the default channel
  and `Annotated[LoggerInterface, Target("<channel>")]` for any other.
- Catalogues: [handlers, processors, formatters](references/handlers.md).
  Configuration as data, the standard-library capture and units of work:
  [configuration](references/configuration.md).

## Log from library or application code

```python
from xtr_logging_contracts import EXCEPTION_KEY, LoggerInterface, NullLogger


class Checkout:
    def __init__(self, logger: LoggerInterface | None = None) -> None:
        self._logger = logger or NullLogger()

    def pay(self, order: Order) -> None:
        try:
            self._gateway.charge(order)
        except GatewayError as error:
            self._logger.error("payment {order} failed", {"order": order.id, EXCEPTION_KEY: error})
```

A library depends on `xtr-logging-contracts` at runtime and keeps `xtr-logging` as a dev
dependency for its tests. An application depends on both. The default of `NullLogger()` is what
lets a caller pass nothing.

Nine methods, all the same shape — `emergency`, `alert`, `critical`, `error`, `warning`,
`notice`, `info`, `debug`, and `log(level, message, context)`. The message is positional-only;
`context` is a `Mapping[str, object]` and may hold anything.

Eight levels, comparable as integers: `DEBUG` 100, `INFO` 200, `NOTICE` 250, `WARNING` 300,
`ERROR` 400, `CRITICAL` 500, `ALERT` 550, `EMERGENCY` 600. Anywhere a level is taken,
`Level.parse` also reads `"error"`, `400` or an RFC 5424 severity; anything else raises
`InvalidLevelError`.

To implement the interface, subclass `AbstractLogger` and write `log()` only. A class handed its
logger later mixes in `LoggerAware`: `self.logger` is a `NullLogger` until `set_logger()`.

## Build a logger

```python
import sys

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

`StreamHandler` takes an open stream or a path; a path opens on first write, parent directories
created. Handlers are consulted first to last; each handles records at its `level` or above, and
`bubble=False` stops a record it handled from reaching the rest:

```python
logger = Logger(
    "app",
    [
        StreamHandler("var/log/errors.log", Level.ERROR, bubble=False),
        StreamHandler(sys.stderr),
    ],
)
```

`logger.with_name("security")` returns a logger on another channel sharing these handlers.
`push_handler()` / `pop_handler()` change the stack. `Logger(..., exception_handler=fn)` receives
anything a handler or processor raises instead of letting it reach the caller.

Each call becomes an immutable `LogRecord`: `datetime`, `channel`, `level`, `message`, `context`
and `extra`.

### Fingers crossed

The handler to run in production: buffer everything, write the lot once one record is bad
enough, so a failed request leaves its whole story and a healthy one leaves nothing.

```python
logger = Logger("app", [FingersCrossedHandler(StreamHandler("var/log/app.log"), Level.ERROR)])
```

Call `reset()` between the requests or messages of a long-running process, or open each one with
`begin_unit()` / `end_unit()`.

## Processors

A processor is any callable `(LogRecord) -> LogRecord`, run once per record and only when some
handler will take it. A `LogRecord` is frozen: return `record.with_extra({...})` rather than
mutating. What a processor adds lands in `extra`, apart from the caller's `context`.

```python
from xtr_logging import LogRecord, as_processor


@as_processor(channel="billing")
def add_tenant(record: LogRecord) -> LogRecord:
    return record.with_extra({"tenant": current_tenant()})
```

`channel=` limits it to one channel, `handler=` attaches it inside a handler instead (and so to
every channel that handler serves), `priority=` runs higher first. A `LoggerFactory` attaches
every declared processor, so import the declaring module.

Ambient context rides along without being passed to every call, separate per thread and per task:

```python
from xtr_logging import ContextVarsProcessor, bound_context

logger = Logger("app", [handler], [ContextVarsProcessor()])

with bound_context({"request_id": request.id, "user": user.id}):
    handle(request)  # every record in here carries both, in extra
```

## Testing

```python
from xtr_logging import Logger, TestHandler
from xtr_logging_contracts import Level

handler = TestHandler()
Checkout(Logger("app", [handler])).pay(order)

assert handler.has_record_that_contains("payment", Level.ERROR)
```

Also `has_records(level)`, `has_record(message, level, context)`,
`has_record_that_matches(pattern, level)`, `has_record_that_passes(predicate, level)`, `records`
and the rendered `formatted`. With a factory, configure a `service` handler and supply a
`TestHandler`, or fetch one by name with `factory.handler("main")`.

Freeze record times without touching the logger:

```python
from xtr_clock import Clock, MockClock

with Clock.using(MockClock("2026-09-24 12:00:00")):
    logger.info("frozen")  # stamped 2026-09-24T12:00:00+00:00
```

## Use in an application

1. **Install** — `uv add "xtr-logging[di]"`.
2. **Activate** — `LoggingBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
   from `xtr_logging.bundle`.
3. **Brings along** — the clock bundle, when installed, so records read the same instant as an
   injected clock.
4. **Configure** — required to see anything: with no configuration there are no handlers, so
   records go nowhere. Put channels and handlers in `<app>/config/logging.py`:

   ```python
   # <app>/config/logging.py
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

5. **Environment** — nothing.
6. **Ignore** — whatever directory the file handlers write to, such as `var/log/`.
7. **Use** — inject `LoggerInterface` for the default channel, and qualify with a channel name
   for any other:

   ```python
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

8. **Check** — `debug:bundles` shows `logging` as `listed` and `active`, and `clock` as
   `required`.
9. **Remove** — drop the `BUNDLES` entry, delete `<app>/config/logging.py`, then
   `uv remove xtr-logging`. Libraries logging through `xtr-logging-contracts` keep working,
   silently.

The bundle registers the `LoggerFactory`, a `LoggerInterface` for the default channel and one
qualified by each channel's name. A `ServiceHandlerSpec`, a `ServiceProcessorSpec`, a `formatter`
given as a string and a fingers-crossed `activation_strategy` all name services the application
registers under `HandlerInterface`, `ProcessorInterface`, `FormatterInterface` or
`ActivationStrategyInterface` with `qualifier=id`; a missing id fails the build with
`UnknownServiceError`. `LoggerFactory` is reset between messages by the kernel's
`ServicesResetter`.

## Errors

`LoggingError` is the base — it lives in `xtr-logging-contracts`, so an application can catch
every logging failure from either package with one name. The ones worth naming:

| Error | Raised when |
| --- | --- |
| `InvalidLevelError` | A value names no level. Also a `ValueError` |
| `InvalidConfigurationError` | Configuration data does not fit, naming the path to what is wrong |
| `UnknownChannelError` | A logger or processor names a channel that is not declared |
| `UnknownHandlerError` | A wrapper, processor or lookup names a handler that is not defined |
| `UnknownServiceError` | Configuration names a service that was not supplied |
| `CaptureConflictError` | A `stdlib` handler is configured while capture is on |

Also `CircularHandlerReferenceError` (wrappers nesting in a loop), `MixedChannelFilterError` (a
channel list mixing `foo` and `!foo`), `InvalidOptionError`, `EmptyStackError` and
`NotProcessableHandlerError`.

## Do not

- Do not interpolate values into the message. `logger.info(f"user {user} in")` loses the
  template and the values a handler wants apart. Write
  `logger.info("user {user} in", {"user": user})` with a `PlaceholderProcessor` attached.
- Do not pass a second positional argument as a format argument: `context` is a mapping, and the
  message is positional-only.
- Do not import `LoggerInterface`, `Level`, `Context`, `NullLogger`, `AbstractLogger` or
  `LoggerAware` from `xtr_logging` — they are `xtr_logging_contracts` names, not re-exported.
- Do not make a library depend on `xtr-logging` to annotate a parameter; depend on
  `xtr-logging-contracts` and let the application wire an implementation.
- Do not format a traceback into the message; put the exception under `EXCEPTION_KEY`.
- Do not mutate a `LogRecord` in a processor; it is frozen. Return `record.with_extra({...})`.
- Do not call `begin_unit()` or `end_unit()` from a handler, a processor or an endpoint — only
  from whatever owns the request, message or command.
- Do not leave a `LoggerFactory` unclosed when it has a `capture` section, even in a test: use
  it as a context manager, or call `close()`.
- Do not suppress ruff's `PLE1205` one call at a time; it reads every `logger.info(...)` as the
  standard library's and misjudges the context mapping. Ignore the rule project-wide.
