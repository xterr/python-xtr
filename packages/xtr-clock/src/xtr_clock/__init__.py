"""A clock an application can be handed, instead of the one it is standing on.

Reading the time is an input like any other, and code that reaches for the
operating system to get it cannot be told what time it is. That is what makes
a test about expiry, backoff or a billing period slow, flaky, or quietly
wrong every March.

Depend on :class:`~xtr_clock.clock_interface.ClockInterface` and the choice
becomes a constructor argument:
:class:`~xtr_clock.system_clock.SystemClock` in production,
:class:`~xtr_clock.monotonic_clock.MonotonicClock` where a duration must be
trusted, :class:`~xtr_clock.mock_clock.MockClock` in a test. What comes back
is always a :class:`~xtr_clock.date_point.DatePoint`: a
:class:`~datetime.datetime` that is always timezone-aware and stays itself
through every operation.

Code that cannot be handed anything asks :meth:`~xtr_clock.clock.Clock.get`,
and a test answers with :func:`~xtr_clock.testing.mock_time`.

Nothing here depends on anything outside the standard library.
"""

from importlib.metadata import PackageNotFoundError, version

from .clock import Clock
from .clock_aware_mixin import ClockAwareMixin
from .clock_interface import ClockInterface, SupportsNow
from .date_point import DatePoint
from .exception import ClockError, InvalidModifierError, InvalidTimezoneError
from .mock_clock import MockClock
from .modifier import apply_modifier
from .monotonic_clock import MonotonicClock
from .now import now
from .system_clock import SystemClock
from .timezone import local_timezone, resolve_timezone

try:
    __version__ = version("xtr-clock")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "Clock",
    "ClockAwareMixin",
    "ClockError",
    "ClockInterface",
    "DatePoint",
    "InvalidModifierError",
    "InvalidTimezoneError",
    "MockClock",
    "MonotonicClock",
    "SupportsNow",
    "SystemClock",
    "__version__",
    "apply_modifier",
    "local_timezone",
    "now",
    "resolve_timezone",
]
