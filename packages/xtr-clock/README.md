<div align="center">

# xtr-clock

**A clock an application can be handed, instead of the one it is standing on.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="core dependencies: 0" src="https://img.shields.io/badge/core%20deps-0-3FB950">
<img alt="coverage 100%" src="https://img.shields.io/badge/coverage-100%25-3FB950">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Reading the time is an input like any other. Code that reaches for the operating system to get
it is code you cannot tell what time it is — so a test about a token expiring in an hour either
waits an hour, or reaches for a library that rewrites the interpreter underneath it.

Take a **clock** as a constructor argument and the choice becomes configuration: the system
clock in production, a frozen one in a test. What comes back is a **`DatePoint`** — a
`datetime`, so nothing downstream has to change.

- 🪶 **No dependencies.** Not one. `zoneinfo`, `contextvars` and `datetime` are already there.
- 🕐 **A `DatePoint` is a `datetime`.** It drops into an ORM column, a serializer, a comparison,
  an existing signature. Adopting this library changes no type you already have.
- 🧭 **Always timezone-aware.** There is no such thing here as an instant whose offset is
  unknown, which is what makes comparing two of them always mean something.
- ⏱️ **Frozen time costs nothing.** `clock.sleep(86400)` returns immediately and the clock is a
  day later.
- 🔀 **Blocking or awaiting.** `sleep()` and `sleep_async()` on the same clock, so one contract
  serves a worker and a web handler.
- 🧩 **Protocol-based.** Every collaborator is a constructor argument, so a DI container can own
  the graph — and a clock from another library satisfies `SupportsNow` as it is.

```python
expires_at = self._clock.now().modify("+1 hour")
```

Whether that is the real hour or an instant one in a test is a constructor argument.

## Install

```sh
uv add xtr-clock                 # everything
uv add "xtr-clock[tzdata]"       # + a timezone database, where the system has none
```

| Extra | Brings | For |
| --- | --- | --- |
| *(none)* | — | The whole library |
| `tzdata` | `tzdata` | Windows, and slim containers that ship no zone database |

Requires Python 3.11+.

## Quick start

A time-sensitive class asks for a clock and nothing else:

```python
from dataclasses import dataclass

from xtr_clock import ClockInterface, DatePoint


@dataclass(frozen=True, slots=True)
class TokenIssuer:
    clock: ClockInterface

    def issue(self) -> DatePoint:
        return self.clock.now().modify("+1 hour")
```

In production it gets the real one:

```python
from xtr_clock import SystemClock

issuer = TokenIssuer(SystemClock())
```

In a test it gets one that stands still, and the test is about the hour rather than spent
waiting for it:

```python
from xtr_clock import MockClock


def test_a_token_expires_in_an_hour() -> None:
    issuer = TokenIssuer(MockClock("2024-04-09 12:00:00"))

    assert issuer.issue().isoformat() == "2024-04-09T13:00:00+00:00"
```

Nothing about `TokenIssuer` changed, and nothing patched the interpreter to get there.

## Clocks

Four, and the differences between them are the point.

| Clock | Reads | Use for |
| --- | --- | --- |
| `SystemClock` | The operating system's wall clock | Production. Recording *when* something happened |
| `MonotonicClock` | A counter that only moves forward | Measuring *how long* something took |
| `MockClock` | Whatever it was told, until told otherwise | Tests |
| `Clock` | Whatever is in force, or a clock from elsewhere | Adapting, and code nothing can be handed to |

Each answers the same four questions:

```python
clock.now()  # a DatePoint, always aware
clock.sleep(2.5)  # block; a MockClock returns at once, 2.5s later
await clock.sleep_async(2.5)  # the same, without holding the event loop
clock.with_timezone("Europe/Paris")  # a copy that reports in another zone
```

`with_timezone` returns a copy, so pinning a zone for one class does not change the time
anybody else reads.

### Wall clock or monotonic

A wall clock jumps. A time daemon corrects a drift, an administrator fixes the date, a zone
changes its mind about daylight saving. Subtract two readings taken either side of one of those
and the duration is wrong — occasionally negative.

`MonotonicClock` anchors to the wall clock once, when it is built, and then reports that anchor
plus however far the machine's monotonic counter has moved. It is the right clock for a timeout
and the wrong one for a timestamp, because it drifts from the wall clock by exactly the
correction it refused to follow.

### A clock from somewhere else

Anything with a `now()` satisfies `SupportsNow`, which is the whole contract for adopting one:

```python
from xtr_clock import Clock

clock = Clock(some_other_libraries_clock)  # now a full ClockInterface
clock.now()  # a DatePoint, whatever it answered with
```

`Clock` fills in what the wrapped object cannot do. Asked to sleep, it hands the request on if
the wrapped clock knows how, and lets real time pass if it does not.

## Instants

`DatePoint` is a `datetime` subclass, which is the most important thing about it. Every method
you already use works, and every result is still a `DatePoint`:

```python
point = clock.now()

point.replace(hour=9)  # DatePoint
point + timedelta(days=1)  # DatePoint
point.astimezone(UTC)  # DatePoint
point.isoformat()  # a string, as always
point < other_datetime  # compares fine
```

It adds two guarantees and three methods.

**It is always timezone-aware.** A naive reading is taken as local time — the reading the
standard library itself picks whenever it has to convert one. So `DatePoint(2024, 4, 9)` carries
a zone, and so does anything `fromisoformat`, `strptime` or `fromtimestamp` produces.

**`now()` reads the clock in force**, not the operating system. That one departure from
`datetime` is deliberate: it means freezing the clock in a test reaches a helper you never got
round to injecting a clock into.

```python
DatePoint.parse("+1 day Europe/Paris")  # the grammar below, against the current clock
point.modify("+1 hour")  # the same, against this instant
point.with_timezone("Asia/Tokyo")  # the same instant, another wall clock
```

`DatePoint.from_datetime(value)` adopts any `datetime` you already have.

> A `DatePoint` is built the way a `datetime` is — `DatePoint(2024, 4, 9)`. The string grammar
> lives on `parse()` and `now()` rather than on the constructor, because `replace`, arithmetic
> and every inherited `from*` method route back through it, and a first argument that is
> sometimes a year and sometimes a sentence makes all of them untypeable.

## The modifier grammar

`'+1 day'` is convenient enough to be worth parsing, and small enough to be worth parsing
ourselves. Five shapes, and anything else is an error:

| Written | Means |
| --- | --- |
| `now` | The reference, untouched |
| `+1 day`, `-2 hours 30 minutes`, `2 days ago` | An offset. Units chain, and may be negative |
| `today`, `tomorrow`, `yesterday`, `midnight`, `noon` | A boundary of the day |
| `2024-04-09`, `2024-04-09 15:00`, `2024-04` | An absolute datetime, in ISO-8601 |
| `Europe/Paris`, `UTC`, `+02:00` | The same instant, read in another zone |

Units are `year`, `month`, `week`, `day`, `hour`, `minute`, `second`, `millisecond` and
`microsecond`, singular or plural, with the obvious short forms (`hr`, `mins`, `secs`). Single
letters are refused: `m` reads as both minute and month, and a modifier should never be a guess.

A zone may trail any of them, and is applied first:

```python
now("+1 day Europe/Paris")  # move to Paris, then add a day there
```

Which is not the same instant as adding a day and then moving — so the order is worth being
explicit about.

### Two rules about arithmetic

**Calendar units keep the wall clock. Durations keep the elapsed time.**

```python
eve = MockClock("2025-03-30 01:00:00", "Europe/Amsterdam").now()  # a spring forward is coming

eve.modify("+1 day")  # 2025-03-31T01:00:00+02:00 — same time tomorrow
eve.modify("+24 hours")  # 2025-03-31T02:00:00+02:00 — 24 real hours later
```

Both are correct; they are answers to different questions. Keeping the wall clock can land on
one that never existed, on the morning an hour went missing, so every result is resolved back
through the instant it names — what comes out is a time that was really on the wall.

**Month arithmetic clamps.** January 31 plus a month is February 28, not March 3, so adding a
month never skips one. Clamping makes month arithmetic non-associative at month ends — two
`'+1 month'` steps from January 31 reach March 28, one `'+2 months'` step reaches March 31 —
which is a property of calendars rather than a defect here.

## Reaching code you cannot hand a clock

Injection is the honest answer and covers most code. It does not cover a module-level helper, a
validator a framework calls, or a function three libraries deep. That code calls `now()`:

```python
from xtr_clock import now

now()  # the current instant, from the clock in force
now("+1 hour")
now("tomorrow")
```

and a test answers by installing a different clock:

```python
from xtr_clock.testing import mock_time

with mock_time("2024-04-09 12:00:00"):
    assert now().hour == 12
```

The clock in force lives in a `ContextVar`, so a scope that installs one does not leak into a
concurrent task that did not, and two tests running side by side cannot see each other's.
Installing also updates a process-wide fallback, so a thread started later — which begins with a
fresh context — still sees the clock the application chose.

`Clock.set(clock)` installs one for good, which is what an application does at startup.
`Clock.using(clock)` installs one for a block and puts the old one back on the way out,
including when the block raises. Prefer `using` everywhere else: `set` has no end, and a test
that forgets to undo it hands the next one a clock it never asked for.

### A class that cannot take a constructor argument

`ClockAwareMixin` gives a class a clock it can be handed, and a default until it is. It defines
no `__init__`, so it composes with anything — including a dataclass:

```python
from xtr_clock import ClockAwareMixin


class AuditLog(ClockAwareMixin):
    def record(self, event: str) -> None:
        self._rows.append((self.now(), event))


log = AuditLog()
log.set_clock(MockClock("2024-04-09 12:00:00"))
```

Until `set_clock` is called it reads whatever is in force, so it works untouched in production
and freezes with everything else in a test.

## Testing your application

Three ways in, depending on how much of the application knows about clocks.

**A class that takes one** needs nothing from this section — hand it a `MockClock`.

**Code that calls `now()`** gets `mock_time`, which installs a frozen clock for a block:

```python
from xtr_clock.testing import mock_time

with mock_time("2024-04-09 12:00:00") as clock:
    assert issue_token().expires_at.hour == 12
    clock.sleep(3600)  # an hour passes; the test does not wait
    assert token_has_expired()
```

`when` may be a string the grammar reads, a `datetime`, or nothing at all to freeze where you
already are. A relative one is read against the clock already in force, so `mock_time("+1 day")`
nested inside the block above lands on the 10th.

**A whole test** can have the fixture. Opt in once, in a `conftest.py`:

```python
pytest_plugins = ["xtr_clock.pytest_plugin"]
```

```python
def test_a_token_expires_in_an_hour(clock: MockClock) -> None:
    token = issue_token()

    clock.sleep(3599)
    assert token.is_valid()
    clock.sleep(2)
    assert not token.is_valid()
```

It is not registered automatically on purpose: a `clock` fixture appearing in every suite that
merely installs this library would collide with the one plenty of suites already have.

A `MockClock` freezes in **UTC** by default, where a real clock is built in the machine's own
zone — a frozen test should not change its answer because of where the laptop running it is.

> In async code prefer `mock_time` inside the coroutine over a fixture that finishes before the
> coroutine starts, so the block and the code it covers share one context.
> `MockClock.sleep_async` advances instantly and yields control once, so the tasks waiting on the
> clock get their turn — which is usually the behaviour the test is there to observe.

## Errors

Everything this library raises derives from `ClockError`, and carries what went wrong as typed
attributes rather than only a message. Both are also `ValueError`s, so code already guarding a
conversion with `except ValueError` keeps working.

| Error | Raised when |
| --- | --- |
| `InvalidModifierError` | The grammar cannot read a modifier. Carries `.modifier` and `.reason` |
| `InvalidTimezoneError` | A timezone is named that this system cannot resolve. Carries `.timezone` |

A typo is refused where it is written rather than resolving to something plausible:

```python
now("+1 dya")  # InvalidModifierError, not silently "now"
```

## Relation to other datetime libraries

This library is about **who tells the time**, not about replacing `datetime`. It deliberately
introduces no datetime type of its own, and the arithmetic it does own is only what the modifier
grammar needs.

If you want a genuinely better datetime — nanosecond precision, naive and aware as separate
types, an explicit choice of what to do with an ambiguous hour —
[whenever](https://github.com/ariebovenberg/whenever) is the one to reach for. It is not so much
an alternative to this library as an orthogonal one, and because a `DatePoint` *is* an aware
`datetime`, the two need no adapter:

```python
from whenever import Instant

moment = Instant(clock.now())  # straight in
later = moment.to_tz("Europe/Paris").add(months=5)  # its arithmetic, its disambiguation rules
back = DatePoint.from_datetime(later.to_stdlib())  # and straight back out
```

`Instant` takes any aware `datetime`. Its `ZonedDateTime` constructor is stricter — it wants a
`zoneinfo.ZoneInfo` exactly — so reach it through `to_tz` as above, or hand it a `DatePoint`
built with a named zone rather than the UTC default.

Prefer `whenever` outright if its types are the ones you want in your domain model; it has its
own way to patch the current time. Prefer this library when you want the clock to be an injected
dependency and `datetime` to stay the type on the boundary. The two compose.

## Layout

```
xtr_clock/
├── clock_interface.py     what a clock answers to — and SupportsNow, the smaller contract
├── date_point.py          an instant: a datetime that stays aware, and stays itself
├── system_clock.py        reads the operating system's wall clock
├── monotonic_clock.py     counts forward, whatever the wall clock does
├── mock_clock.py          stands still until a test moves it
├── clock.py               the clock in force, and the adapter that fits a foreign one
├── clock_aware_mixin.py   for a class that cannot take a constructor argument
├── now.py                 now() — the one-call front door
├── modifier.py            the little grammar '+1 day' is written in
├── timezone.py            turning a zone's name into a zone, in one place
├── testing.py             freeze the clock for a block, restore it after
├── pytest_plugin.py       the same as a fixture, opt-in
└── exception/             one error per module, all a ClockError
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-clock`; run the commands below from there. The `python-xtr-clock` repository is a
read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check src tests
uv run ruff format --check src tests
uv run ty check
uv run basedpyright
uv run coverage run -m pytest && uv run coverage report
```

Two type checkers on purpose — they disagree often enough to be worth both. Both run strict on
the tests too, with nothing suppressed.

The suite mirrors the source tree: `tests/unit/` holds a `test_<module>.py` for each module,
testing it alone; `tests/integration/` holds what needs a fresh interpreter — that the fixture
is invisible until a suite opts in, and that importing the library pulls in nothing but the
standard library. Statement and branch coverage are both 100%, measured with `coverage run`
rather than `pytest --cov`, which starts too late to see a module's import.

## License

[MIT](LICENSE) © xterr
