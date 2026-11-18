<div align="center">

# xtr-stopwatch

**Where the time went: named events, grouped by category, nested in sections — one set per unit of work.**

<img alt="python 3.14+" src="https://img.shields.io/badge/python-%E2%89%A5%203.14-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

"This request took 400 ms" is a start; "the listeners took 30, the queries 300, and the template
the rest" is an answer. Getting there takes every piece of work timed under a name, a kind, and
one shared starting point, so the pieces can be laid side by side on a timeline.

- ⏱️ **Events by name.** Start and stop `"load"`; run it three times and it is one event with
  three periods.
- 🏷️ **Categories.** Each event says what kind of work it is — `"orm"`, `"event_listener"`,
  `"template"` — so a timeline can colour and filter by kind.
- 🪆 **Sections.** Open one per request: every event in it is measured from the section's own
  origin, and the section is stored under an id once it closes.
- 🔀 **Concurrent units of work stay apart.** What is timed belongs to the calling context, so
  two requests served at once each see only their own events.
- 🕰️ **A clock you can freeze.** Readings come from an
  [xtr-clock](../xtr-clock) clock — monotonic by default, a `MockClock` in a test.

## Install

```sh
uv add xtr-stopwatch
```

Requires Python 3.14.4+.

## Quick start

```python
from xtr_stopwatch import Stopwatch

stopwatch = Stopwatch()

stopwatch.open_section()
event = stopwatch.start("load-books", "orm")
...  # the work
event.stop()
stopwatch.stop_section("request-42")

for name, event in stopwatch.get_section_events("request-42").items():
    print(name, event.category, f"{event.get_duration():.1f} ms")
```

## Events

`start(name, category=None)` opens a period of the event `name` in the current section and
returns the event; `stop(name)` closes the period opened last. Starting a running event again
opens a second, nested period. `lap(name)` closes one period and opens the next at the same
instant.

Keep the event `start` returns and stop *it* when the code that started it is the code that
ends it: the object stays the same even if the context is [reset](#units-of-work) in between,
so its period still closes.

| `StopwatchEvent` | Answers |
|---|---|
| `name`, `category`, `origin` | what it is called, what kind of work it is (`"default"` when none was given), the instant its readings count from — milliseconds since the epoch |
| `get_periods()` | every closed period: `start`, `end`, `duration`, in milliseconds from `origin` |
| `get_start_time()`, `get_end_time()` | when it first began, when its last closed period ended |
| `get_duration()` | the time spent in every period, open ones counted up to now |
| `is_started()`, `ensure_stopped()` | whether a period is open; close every open one |
| `to_dict()` | all of the above as plain data, for JSON |

## Sections

`open_section()` opens a section inside the current one; `stop_section(section_id)` closes the
current section and stores it under `section_id`, after which
`get_section_events(section_id)` returns its events by name. The events of a section all count
from the instant it opened, which is what puts them on one axis.

Opening a section starts `SECTION_EVENT` (`"__section__"`) in it and `SECTION_CHILD_EVENT`
(`"__section__.child"`, category `"section"`) in its parent, and closing it stops both — the
section's own duration is one of its events, and the parent records where the child sat in its
own time. `open_section(section_id)` reopens a stopped child of the current section, adding a
period to it.

Outside any section, events go to the root section, stored as `ROOT` (`"__root__"`), whose
events each count from the instant they first started.

`has_open_section()` tells whether the calling context has a section open, without starting
anything. Code that times what it does on a stopwatch it shares — every listener a dispatcher
runs — asks it first, so a context no unit of work times in, a worker's own loop, never
accumulates events.

## Units of work

Everything a stopwatch times belongs to the calling context — the same `contextvars` mechanism
that keeps a server's concurrent requests apart — so
one stopwatch shared by a whole application gives every request only its own sections. Code
run in a copy of that context, such as a synchronous function a worker thread runs, times into
the same sections.

`reset()` starts the calling context afresh, with nothing timed. A unit of work calls it as it
begins; other contexts are untouched.

## Testing

Freeze time with [xtr-clock](../xtr-clock)'s `MockClock` and move it with `sleep`:

```python
from xtr_clock import MockClock
from xtr_stopwatch import Stopwatch

clock = MockClock("2026-01-01 00:00:00")
stopwatch = Stopwatch(clock)

stopwatch.start("load")
clock.sleep(0.004)
assert stopwatch.stop("load").get_duration() == 4.0
```

## Errors

Everything this library raises derives from `StopwatchError`.

| Error | Raised when |
|---|---|
| `EventNotStartedError` | an event is stopped or lapped while it is not running |
| `UnknownEventError` | `get_event` names an event the current section never started; also a `LookupError` |
| `NoStartedSectionError` | `stop_section` is called with only the root open |
| `UnknownSectionError` | `open_section(section_id)` names no child of the current section; also a `LookupError` |

## Layout

```
xtr_stopwatch/
├── stopwatch.py          Stopwatch, the sections of the calling context
├── section.py            Section, the events sharing one origin
├── stopwatch_event.py    StopwatchEvent, one named thing and its periods
├── stopwatch_period.py   StopwatchPeriod, one start and its stop
└── exception/            StopwatchError, the root of everything this library raises
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-stopwatch`; run the commands below from there.

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
