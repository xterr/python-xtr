# Configuration, the standard library, and units of work

## Logging described as data

`LoggingConfig` names channels, handlers and processors. It builds nothing; a `LoggerFactory`
does.

```python
from xtr_logging import LoggerFactory, LoggingConfig
from xtr_logging.config import (
    ConsoleHandlerConfig,
    FingersCrossedHandlerConfig,
    PlaceholderProcessorConfig,
    StreamHandlerConfig,
)

CONFIG = LoggingConfig(
    channels=("security", "billing"),
    handlers={
        "main": FingersCrossedHandlerConfig(action_level="error", handler="file"),
        "file": StreamHandlerConfig(path="var/log/prod.log"),
        "console": ConsoleHandlerConfig(channels=("!event",)),
    },
    processors=(PlaceholderProcessorConfig(),),
)

factory = LoggerFactory(CONFIG)
security = factory.logger("security")
```

Fields: `handlers`, `channels`, `processors`, `default_channel` (`"app"`) and `capture`. Read
`all_channels`, `top_level_handlers` and `nested_handlers` as properties, not calls.

Or read it from a file:

```python
config = LoggingConfig.from_mapping(tomllib.loads(Path("logging.toml").read_text()))
```

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

Handler `type` values: `stream`, `rotating_file`, `syslog`, `console`, `null`, `stdlib`,
`service`, `fingers_crossed`, `buffer`, `filter`, `deduplication`, `sampling`, `queue`, `group`,
`whatfailuregroup`, `fallbackgroup`. Processor `type` values: `placeholder`, `context_vars`,
`uid`, `introspection`, `hostname`, `process_id`, `tags`, `service`.

The rules:

- **Channels.** `default_channel` always exists. `channels` adds more, and a channel named in any
  handler's `channels` is declared too. Asking for any other raises `UnknownChannelError`.
  `config.with_channels("mail")` returns a copy declaring more — what a bundle calls from
  `prepend_extension` to claim a channel of its own.
- **Channel filters.** `channels="security"` or `["a", "b"]` includes; `"!event"` or
  `["!a", "!b"]` excludes. Mixing raises `MixedChannelFilterError`. A filter applies only to a
  handler on a channel's stack, never to one nested inside another handler.
- **Nesting.** A wrapper names what it wraps (`handler="file"`, `members=["a", "b"]`). A handler
  named that way, or marked `nested`, is kept off every channel's stack.
- **Priority.** Higher is consulted first; ties keep declaration order.
- **Services.** `type="service"` names an object you supply, as do a formatter given by name and
  an `activation_strategy`:

  ```python
  LoggerFactory(CONFIG, services=Services(handlers={"sentry": sentry_handler}))
  ```

Everything is checked as the configuration is made: a typo'd key, an unknown level or a value of
the wrong type raises `InvalidConfigurationError` naming the path; a wrapper naming a missing
handler raises `UnknownHandlerError`; wrappers in a loop raise `CircularHandlerReferenceError`.

## The factory

- Builds every handler once and shares each between channels. Files open on first write.
- `factory.logger(channel=None)`, `factory.channels`, `factory.handler(name)`,
  `factory.capture`.
- `reset()` ends a unit of work. `close()` writes whatever is buffered or queued and releases the
  capture — use the factory as a context manager, or close it on shutdown.
- `set_verbosity(Verbosity.from_count(args.verbose, quiet=args.quiet, silent=args.silent))` sets
  every console handler at once: `--silent` prints nothing, `-q` errors and up, no flag warnings
  and up, `-v` notices, `-vv` info, `-vvv` everything.
- `set_console_stream(stream, colors=...)` points every console handler elsewhere, with colours
  forced on or off.

## Capturing the standard library

Third-party packages log through `logging`. A `capture` section routes their records into your
channels instead:

```toml
channels = ["db"]

[capture]
level = "warning"          # threshold for every stdlib logger not listed below

[capture.loggers]
httpx = "info"             # its own level; httpx._client and every child follow it
"sqlalchemy.engine" = { level = "warning", channel = "db" }
```

Captured records become records on a channel — `default_channel` unless an entry says otherwise
— and run through its processors and handlers like any other. `extra=` values become context,
`exc_info` becomes `context["exception"]`, and the original time is kept. A logger's entry covers
its children; the most specific name wins.

Nothing is written twice: the capture takes the standard library's output over rather than
adding a handler beside it. Existing handlers are moved aside, every logger propagates to the
root, a handler attached while capture is on is held aside, and a record from a logger
reconfigured not to propagate is captured rather than printed raw.

The factory installs the capture as it is built and gives everything back on `close()` — so a
factory with a `capture` section must be closed, even in a test. A `stdlib` handler cannot be
combined with a capture: the configuration refuses it with `CaptureConflictError`.

Without a factory:

```python
from xtr_logging.bridge.stdlib import StdlibCapture

with StdlibCapture(logger, levels={"httpx": "info"}, routes={"sqlalchemy": db_logger}):
    serve()
```

The other way round, `StdlibHandler` hands records to a standard-library logger, and
`StdlibLogger` puts `LoggerInterface` in front of a plain `logging.Logger`.

## Units of work

A unit of work is one request, message or command. Some logging state belongs to it rather than
to the process: the id tying its records together, a fingers-crossed buffer, a deduplication
batch.

```python
from xtr_logging import begin_unit, end_unit

begin_unit()
try:
    handle(request)
finally:
    end_unit()
```

`begin_unit()` ends any unit still open first, so a caller that forgot `end_unit()` cannot leak
one unit's state into the next. Call them only from whatever owns the unit — never from a
handler, a processor or an endpoint.

A handler or processor keeps its own per-unit state with
`unit_state(owner, factory, on_end=None)`: the first call in a unit builds it, every later call
returns the same object, and `on_end` is registered once and called with that state as the unit
ends. Distinct owners keep distinct state. Outside a unit it returns `None`, and the owner
behaves as if unbuffered.

A unit lives in a `ContextVar`, copied into each thread and task, so two requests handled at once
keep their own with no lock. The unit object is shared by every context copied from the one that
opened it, so state is mutated in place. `QueueHandler` carries each record's context across to
its background thread, so a record buffered under one unit is written as though still inside it.
