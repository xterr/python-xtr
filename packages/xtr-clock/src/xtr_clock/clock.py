"""The clock in force, and the adapter that makes a foreign one fit.

Injecting a clock is the honest way to make a class testable, and most of
this library exists to support it. But some code cannot be handed anything —
a module-level helper, a validator called by a framework, a function three
libraries deep. That code asks :meth:`Clock.get`, and a test answers by
installing another clock with :meth:`Clock.using`.

The clock in force is held in a :class:`~contextvars.ContextVar`, so a
scope that installs one does not leak into a concurrent task that did not,
and two tests running side by side cannot see each other's. Installing also
updates a process-wide fallback, so a thread started later — which begins
with a fresh context — still sees the clock the application chose.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar, Self, final

from .clock_interface import ClockInterface, SupportsNow
from .date_point import DatePoint
from .system_clock import SystemClock
from .timezone import resolve_timezone

if TYPE_CHECKING:
    from collections.abc import Generator
    from datetime import tzinfo

__all__ = ["Clock"]


@final
class Clock:
    """The clock in force, and a clock that reads it.

    As a class it is the registry: :meth:`get` answers with whatever clock
    is in force, :meth:`set` installs one for good, :meth:`using` installs
    one for a scope.

    As an instance it is a clock in its own right, and a useful one twice
    over. Built around an object that can only say :meth:`~SupportsNow.now`,
    it fills in the rest of the contract. Built around nothing, it forwards
    to whatever is in force at the moment each question is asked — so a
    class handed one at startup reads a clock a test installs later.

    Prefer taking a :class:`~xtr_clock.clock_interface.ClockInterface` as a
    constructor argument. Reach for this only where nothing can be handed
    in.
    """

    _current: ClassVar[ContextVar[ClockInterface | None]] = ContextVar(
        "xtr_clock_current",
        default=None,
    )
    _fallback: ClassVar[ClockInterface | None] = None

    __slots__ = ("_clock", "_timezone")

    _clock: SupportsNow | None
    _timezone: tzinfo | None

    def __init__(
        self,
        clock: SupportsNow | None = None,
        timezone: str | tzinfo | None = None,
    ) -> None:
        """Wrap ``clock``, or the clock in force when none is given.

        Args:
            clock: The clock to read. ``None`` reads whichever clock is in
                force each time a question is asked, rather than the one in
                force now.
            timezone: A zone to pin every reading to. ``None`` reports
                instants in whatever zone the wrapped clock used.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        self._clock = clock
        self._timezone = resolve_timezone(timezone) if timezone is not None else None

    @classmethod
    def get(cls) -> ClockInterface:
        """Return the clock in force.

        A scope opened by :meth:`using` wins; otherwise whatever :meth:`set`
        installed; otherwise a :class:`~xtr_clock.system_clock.SystemClock`,
        built once and kept.
        """
        if (scoped := Clock._current.get()) is not None:
            return scoped

        if Clock._fallback is None:
            Clock._fallback = SystemClock()

        return Clock._fallback

    @classmethod
    def set(cls, clock: SupportsNow) -> None:
        """Install ``clock`` as the clock in force, until something replaces it.

        An object that only answers :meth:`~SupportsNow.now` is wrapped so
        it satisfies the whole contract.

        Prefer :meth:`using` in a test: this one has no end, and a test that
        forgets to undo it hands the next one a clock it never asked for.
        """
        Clock._fallback = _adapt(clock)
        _ = Clock._current.set(Clock._fallback)

    @classmethod
    @contextmanager
    def using(cls, clock: SupportsNow) -> Generator[ClockInterface, None, None]:
        """Install ``clock`` for the duration of a ``with`` block.

        The previous clock comes back on the way out, including when the
        block raises.

        Args:
            clock: The clock to install. An object that only answers
                :meth:`~SupportsNow.now` is wrapped.

        Yields:
            The clock as installed, which is ``clock`` itself unless it had
            to be wrapped.
        """
        resolved = _adapt(clock)
        previous = Clock._fallback
        token = Clock._current.set(resolved)
        Clock._fallback = resolved
        try:
            yield resolved
        finally:
            Clock._current.reset(token)
            Clock._fallback = previous

    @property
    def timezone(self) -> tzinfo | None:
        """The zone readings are pinned to, or ``None`` to follow the clock read."""
        return self._timezone

    def now(self) -> DatePoint:
        """Return the current instant, as the clock being read tells it."""
        moment = DatePoint.from_datetime(self._target().now())

        return moment.with_timezone(self._timezone) if self._timezone is not None else moment

    def sleep(self, seconds: float) -> None:
        """Block for ``seconds``, the way the clock being read does.

        A clock that only answers :meth:`~SupportsNow.now` cannot say how to
        wait, so real time is what passes.
        """
        target = self._target()
        if isinstance(target, ClockInterface):
            target.sleep(seconds)
        else:
            SystemClock().sleep(seconds)

    async def sleep_async(self, seconds: float) -> None:
        """Wait ``seconds`` the way the clock being read does, without blocking."""
        target = self._target()
        if isinstance(target, ClockInterface):
            await target.sleep_async(seconds)
        else:
            await SystemClock().sleep_async(seconds)

    def with_timezone(self, timezone: str | tzinfo) -> Self:
        """Return the same clock pinning every reading to ``timezone``.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        return type(self)(self._clock, timezone)

    def _target(self) -> SupportsNow:
        """Return the clock to read: the wrapped one, or the one in force."""
        if self._clock is not None:
            return self._clock

        current = Clock.get()

        # An empty Clock installed as the clock in force would otherwise ask
        # itself what time it is, and never come back.
        return SystemClock() if current is self else current

    def __repr__(self) -> str:
        """Return a reading that names what is wrapped and any pinned zone."""
        pinned = f", {self._timezone!s}" if self._timezone is not None else ""

        return f"{type(self).__name__}({self._clock!r}{pinned})"


def _adapt(clock: SupportsNow) -> ClockInterface:
    """Return ``clock`` as a full contract, wrapping it only if it is not one."""
    return clock if isinstance(clock, ClockInterface) else Clock(clock)
