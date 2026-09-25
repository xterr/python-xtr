<div align="center">

# xtr-logging-contracts

**The logging contract, and nothing else — so a library that logs installs nothing else.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="core dependencies: 1" src="https://img.shields.io/badge/core%20deps-1-3FB950">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A library that logs should not decide where records go. It takes a `LoggerInterface`, defaults to
a `NullLogger`, and leaves handlers, formatters and configuration to the application that wires
it.

Which means a library needs the *contract*, not an implementation — and should not pay for one.
Depending on [xtr-logging](https://github.com/xterr/python-xtr-logging) to annotate one parameter
drags in a JSON codec, a clock and seventeen handlers the library never touches. This package is
that dependency, reduced to what the seam is actually made of:

- 🧩 **`LoggerInterface`** — eight severities plus `log()`, with a context mapping.
- 🕳️ **`NullLogger`** — what makes logging optional for your callers.
- 🪜 **`Level`** — the eight RFC 5424 severities, comparable as integers.
- 🗂️ **`Context`** — the mapping every method takes, and the key an exception goes under.
- 🪶 **One dependency** — `typing-extensions`, for `@override` on 3.11.

```python
from xtr_logging_contracts import LoggerInterface, NullLogger


class Checkout:
    def __init__(self, logger: LoggerInterface | None = None) -> None:
        self._logger = logger or NullLogger()

    def pay(self, order: Order) -> None:
        self._logger.error("payment {order} failed", {"order": order.id})
```

## Install

```sh
uv add xtr-logging-contracts
```

Requires Python 3.11+.

## Who installs what

|  | Depends on |
| --- | --- |
| **A library that logs** | `xtr-logging-contracts` at runtime, `xtr-logging` as a dev dependency — its tests build real loggers and assert on a `TestHandler`. |
| **An application** | `xtr-logging`, which implements this contract and wires channels, handlers and processors from configuration. |

`xtr-logging` **re-exports** every symbol here rather than redefining it, so
`xtr_logging.LoggerInterface is xtr_logging_contracts.LoggerInterface`. That identity is what lets
a container register a logger under the interface and a library, which never imported
`xtr-logging`, receive it.

## The interface

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
- An exception to report goes under `context["exception"]`.
- `{key}` placeholders in the message are filled from context downstream, not by the logger, so a
  handler can still see the template and the values apart.

`AbstractLogger` implements the eight severity methods on top of `log()`, so an implementation
writes one method. `LoggerAware` gives a class a `logger` that is a `NullLogger` until
`set_logger()` is called.

> ruff's `PLE1205` assumes every `logger.info(...)` is the standard library's and flags the
> context mapping as a stray format argument. Ignore it in projects using this interface.

### Levels

| Level | Value | RFC 5424 | | Level | Value | RFC 5424 |
| --- | --- | --- | --- | --- | --- | --- |
| `DEBUG` | 100 | 7 | | `ERROR` | 400 | 3 |
| `INFO` | 200 | 6 | | `CRITICAL` | 500 | 2 |
| `NOTICE` | 250 | 5 | | `ALERT` | 550 | 1 |
| `WARNING` | 300 | 4 | | `EMERGENCY` | 600 | 0 |

Anywhere a level is accepted, `Level.parse` reads it: a `Level`, its value, an RFC 5424 severity,
or a name in any case (`"error"`). Anything else raises `InvalidLevelError`.

### Context

`Context` is `Mapping[str, object]` — the second argument to every method above. Values are
`object` because a caller may log anything; whatever writes the record normalises what it cannot
serialise rather than refusing it. An exception to report goes under `EXCEPTION_KEY`:

```python
from xtr_logging_contracts import EXCEPTION_KEY

logger.error("payment failed", {"order": order.id, EXCEPTION_KEY: error})
```

## What is not here

Everything that *acts* on what was logged: `LogRecord`, `Logger`, `LoggerFactory`,
`LoggingConfig`, the seventeen handlers, the processors, the formatters, ambient
`bound_context()`, and the standard-library bridge. All of that is
[xtr-logging](https://github.com/xterr/python-xtr-logging).

`LogRecord` in particular belongs there, not here: it appears in no signature above. A library
that logs never builds one or sees one — it is made inside the logger and consumed by handlers
and processors, which are implementation.

`HandlerInterface`, `ProcessorInterface` and `FormatterInterface` are deliberately absent for the
same reason, plus one more: nothing outside `xtr-logging` implements them yet, and a contract
package earns its stability by staying small. They move here when a third-party handler needs
them — and `LogRecord` would move with them.

## Errors

| Error | Raised when |
| --- | --- |
| `LoggingError` | Never directly — the base every logging error derives from, `xtr-logging`'s included |
| `InvalidLevelError` | A value names no level (also a `ValueError`) |

## Development

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
