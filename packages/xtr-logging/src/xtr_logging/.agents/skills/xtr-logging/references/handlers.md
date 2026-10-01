# Handlers, processors and formatters

Everything here is imported from `xtr_logging`.

## Handlers

| Handler | Does |
| --- | --- |
| `StreamHandler` | Writes to a stream or a file, opened on first write, parent directories created |
| `RotatingFileHandler` | One file per day, or any `date_format`, keeping the newest `max_files` |
| `SyslogHandler` | Syslog over UDP or a socket such as `/dev/log`, with the right severity |
| `ConsoleHandler` | Standard error, or any stream set later; its level follows `-v` verbosity, coloured on a terminal |
| `NullHandler` | Swallows records at its level |
| `TestHandler` | Keeps records in memory for assertions |
| `FingersCrossedHandler` | Buffers everything; writes it all once one record is bad enough |
| `BufferHandler` | Buffers records and writes them as a batch on `close()` |
| `GroupHandler` | Sends every record to every member |
| `WhatFailureGroupHandler` | A group where a failing member never stops the others |
| `FallbackGroupHandler` | Tries members in order until one does not raise; a member below its level counts as done |
| `FilterHandler` | Passes a level range, or a list of levels, to the handler it wraps |
| `DeduplicationHandler` | Drops a buffered batch whose errors were all written in the last `time` seconds |
| `SamplingHandler` | Passes one record in `factor` |
| `QueueHandler` | Writes on a background thread, so logging never waits on I/O |
| `StdlibHandler` | Hands records to a standard-library logger (in `xtr_logging.bridge.stdlib`) |

Every handler takes `level` and `bubble`. A record at or above `level` is handled; with
`bubble=False` it then goes no further down the stack.

Writing your own: subclass `AbstractHandler` for full control, or `AbstractProcessingHandler`
to get formatting and handler-attached processors and write only `write(record, formatted)`.
`HandlerInterface`, `FormattableHandlerInterface`, `ProcessableHandlerInterface` and
`ActivationStrategyInterface` are the protocols a container registers against.

### Fingers-crossed options

```python
FingersCrossedHandler(
    handler,  # or a factory that builds it lazily
    activation_strategy=Level.ERROR,  # a level, or an ActivationStrategyInterface
    buffer_size=0,  # 0 keeps everything until activation
    bubble=True,
    stop_buffering=True,  # pass straight through once activated
    passthru_level=None,  # keep records at this level even untriggered
)
```

`ErrorLevelActivationStrategy` is what a bare level becomes.
`ChannelLevelActivationStrategy` sets a different trigger per channel.

## Processors

A processor is any callable `(LogRecord) -> LogRecord`. `ProcessorInterface` is the protocol.

| Processor | Adds |
| --- | --- |
| `PlaceholderProcessor` | Fills `{placeholders}` in the message from context |
| `ContextVarsProcessor` | Whatever is bound with `bind_context()` / `bound_context()` |
| `UidProcessor` | A random id shared by every record until `reset()` |
| `IntrospectionProcessor` | The file, line, function and module that logged |
| `HostnameProcessor` | The machine |
| `ProcessIdProcessor` | The process |
| `TagProcessor` | A fixed list of tags |

Ambient context: `bind_context(values)`, `unbind_context(*keys)`, `clear_context()`,
`current_context()`, and `bound_context(values)` as a context manager. It lives in a context
variable, so it is separate per thread and per asyncio or anyio task.

`as_processor` declares one into `default_processor_registry()`, or into a `ProcessorRegistry`
passed as `registry=`. A `LoggerFactory` attaches every declaration it finds; a kernel also
instantiates a decorated *class* as a service.

## Formatters

| Formatter | Renders |
| --- | --- |
| `LineFormatter` | `[%datetime%] %channel%.%level_name%: %message% %context% %extra%` |
| `JsonFormatter` | One JSON object per record; a batch as lines, or as one array with `batch_mode=JsonBatchMode.JSON` |
| `ConsoleFormatter` | A short line with the level coloured |

`LineFormatter` also knows `%level%` and `%context.KEY%` / `%extra.KEY%` for a single entry. It
keeps each record on one line unless `allow_inline_line_breaks` is set, and prints tracebacks
when `include_stacktraces` is set.

`Normalizer`, which both build on, reduces any value to plain `Normalized` data, cutting nesting
and collections short at a limit — so a value that cannot be serialised is described rather than
making the log call fail.

`FormatterInterface` is the protocol a container registers a formatter service against.
