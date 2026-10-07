---
name: xtr-clock
description: How to read, inject and freeze time with xtr-clock. Use when code needs the current time, timestamps, expiry or durations, timezone handling, relative dates such as "+1 day", or a test that must freeze or advance time; also when adding ClockBundle to an application on xtr-dependency-injection.
---

# xtr-clock

Time is an input. Code takes a clock, the application decides which one, and a test hands it a
frozen one. Every reading is a `DatePoint` — a timezone-aware `datetime` subclass, so it goes
anywhere a `datetime` goes.

## Quick reference

- Take a `ClockInterface` as a constructor argument; call `clock.now()`. Never call
  `datetime.now()`, `datetime.utcnow()` or `time.time()` in code that should be testable.
- Production: `SystemClock()`. Durations and timeouts: `MonotonicClock()`. Tests: `MockClock(...)`.
- Code that cannot be handed a clock (module helpers, validators): `from xtr_clock import now`.
- Relative times: `clock.now().modify("+1 hour")`, `now("tomorrow")`, `DatePoint.parse("+1 day UTC")`.
- Freeze for a block: `from xtr_clock.testing import mock_time`.
- In an application: activate `ClockBundle`, inject `ClockInterface`.

## Inject a clock

```python
from dataclasses import dataclass

from xtr_clock import ClockInterface, DatePoint


@dataclass(frozen=True, slots=True)
class TokenIssuer:
    clock: ClockInterface

    def issue(self) -> DatePoint:
        return self.clock.now().modify("+1 hour")
```

Every clock answers the same four calls:

```python
clock.now()  # DatePoint, always aware
clock.sleep(2.5)  # MockClock returns at once and moves 2.5s forward
await clock.sleep_async(2.5)  # same, without blocking; waits through anyio, so any backend works
clock.with_timezone("Europe/Paris")  # a copy; the original is unchanged
```

Pick the clock by question:

| Clock | Use for |
| --- | --- |
| `SystemClock` | Recording *when* something happened |
| `MonotonicClock` | Measuring *how long* something took — never for stored timestamps |
| `MockClock` | Tests; freezes in UTC unless given a zone |
| `Clock` | The clock in force, or an adapter around any object with `now()` (`SupportsNow`) |

## Relative times

The modifier grammar accepts five shapes; anything else raises `InvalidModifierError`:

| Written | Means |
| --- | --- |
| `now` | Unchanged |
| `+1 day`, `-2 hours 30 minutes`, `2 days ago` | An offset; units chain |
| `today`, `tomorrow`, `yesterday`, `midnight`, `noon` | A day boundary |
| `2024-04-09`, `2024-04-09 15:00` | An absolute ISO-8601 datetime |
| `Europe/Paris`, `UTC`, `+02:00` | The same instant in another zone |

- Single-letter units (`m`, `h`) are refused — write `min`, `hr`, `hours`.
- A trailing zone is applied **first**: `"+1 day Europe/Paris"` moves to Paris, then adds a day.
- Calendar units keep the wall clock (`+1 day` across a DST change is "same time tomorrow");
  durations keep elapsed time (`+24 hours`).
- Months clamp: January 31 `+1 month` is February 28/29.
- Stepping through a calendar in code: `shift_calendar(moment, months=1)`.

## Code that cannot take a clock

```python
from xtr_clock import now

expires = now("+1 hour")  # reads the clock in force, not the OS
```

The clock in force lives in a `ContextVar`. Install one with:

- `Clock.set(clock)` — for good, at application startup only.
- `with Clock.using(clock):` — for a block; restored even on error. Prefer this.
- `restore = Clock.install(clock)` — until `restore()` is called, for lifetimes that are not a block.

A class that cannot take a constructor argument mixes in `ClockAwareMixin` and calls `self.now()`;
`set_clock(...)` replaces its clock.

## Testing

```python
from xtr_clock import MockClock
from xtr_clock.testing import mock_time


def test_issue() -> None:
    issuer = TokenIssuer(MockClock("2024-04-09 12:00:00"))
    assert issuer.issue().isoformat() == "2024-04-09T13:00:00+00:00"


def test_helper_code() -> None:
    with mock_time("2024-04-09 12:00:00") as clock:
        clock.sleep(3600)  # an hour passes instantly
        assert now().hour == 13
```

- A `clock` fixture is available after opting in from `conftest.py`:
  `pytest_plugins = ["xtr_clock.pytest_plugin"]`. It is never registered automatically.
- In async tests, call `mock_time` inside the coroutine so the block and the code share a context.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`ClockBundle`, or leaves it out when another bundle requires it (the logging bundle does). That is
the steps below a recipe can do; the others it prints for you to make.

1. **Install** — `uv add "xtr-clock[di]"`; add the `tzdata` extra on Windows or slim containers.
2. **Activate** — usually nothing: the logging bundle requires it. Otherwise add
   `ClockBundle: {"all": True}` to `BUNDLES` in `<app>/bundles.py`
   (`from xtr_clock.bundle import ClockBundle`).
3. **Configure** — optional; with no configuration it reports in the machine's zone:

   ```python
   # <app>/config/clock.py
   from xtr_dependency_injection import configure
   from xtr_clock.bundle import ClockConfig


   @configure
   def clock() -> ClockConfig:
       return ClockConfig(timezone="UTC")
   ```

   `ClockConfig` resolves the zone as it is built, so an unknown one raises
   `InvalidTimezoneError` at build time rather than on the first reading.

4. **Use** — inject `ClockInterface`. The bundle also installs the same clock as the clock in
   force, so `now()` and the injected clock agree.
5. **Test** — replace the `Clock` service:
   `boot_for_test(kernel, overrides={Clock: Clock(MockClock("2026-01-01"), "UTC")})`.
6. **Check** — `debug:bundles` shows `clock` as `active`.
7. **Remove** — drop the `BUNDLES` entry and `<app>/config/clock.py`, then `uv remove xtr-clock`,
   unless xtr-logging is installed (it depends on this package).

## Errors

Both derive from `ClockError` and from `ValueError`:

- `InvalidModifierError` — unreadable modifier (`.modifier`, `.reason`).
- `InvalidTimezoneError` — unknown zone (`.timezone`); install the `tzdata` extra if the system has no zone database.

## Do not

- Do not use naive datetimes; a `DatePoint` is always aware, and comparing aware with naive fails.
- Do not call `Clock.set()` in tests — it never ends; use `mock_time` or `Clock.using`.
- Do not use `MonotonicClock` for timestamps you store or show.
- Do not patch `datetime` or the interpreter to freeze time.
