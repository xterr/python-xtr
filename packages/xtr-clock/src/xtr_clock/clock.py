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

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar, Self, final, override

from .clock_interface import ClockInterface, SupportsNow
from .date_point import DatePoint
from .system_clock import SystemClock
from .timezone import resolve_timezone

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
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

    _current: ClassVar[ContextVar[ClockInterface | _Installed | None]] = ContextVar(
        "xtr_clock_current",
        default=None,
    )
    # What a context that installed nothing reads: the innermost install still
    # active, else what :meth:`set` put in force. A stack rather than one slot,
    # so installs that end out of the order they began — concurrent tasks —
    # leave the fallback on the one still running, never on a finished one.
    _base: ClassVar[ClockInterface | None] = None
    _active: ClassVar[list[_Installed]] = []
    _active_lock: ClassVar[threading.Lock] = threading.Lock()

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
        scoped = Clock._current.get()
        # An installation restored since — from another context, maybe — gives way.
        while isinstance(scoped, _Installed):
            if scoped.active:
                return scoped.clock
            scoped = scoped.previous
        if scoped is not None:
            return scoped

        with Clock._active_lock:
            if Clock._active:
                return Clock._active[-1].clock
            if Clock._base is None:
                Clock._base = SystemClock()
            return Clock._base

    @classmethod
    def set(cls, clock: SupportsNow) -> None:
        """Install ``clock`` as the clock in force, until something replaces it.

        An object that only answers :meth:`~SupportsNow.now` is wrapped so
        it satisfies the whole contract.

        Prefer :meth:`using` in a test: this one has no end, and a test that
        forgets to undo it hands the next one a clock it never asked for.
        """
        resolved = _adapt(clock)
        with Clock._active_lock:
            # Inside an open scope it replaces that scope's clock, which the
            # scope's end then takes away — as a test's ``with`` undoes it.
            if Clock._active:
                Clock._active[-1].clock = resolved
            else:
                Clock._base = resolved
        _ = Clock._current.set(resolved)

    @classmethod
    def install(cls, clock: SupportsNow) -> Callable[[], None]:
        """Install ``clock`` until the returned function is called, which puts the previous back.

        :meth:`using` for a lifetime that is not a ``with`` block — a
        kernel's, from boot to shutdown. Its end may run in another task or
        thread than its start, which a ``with`` block's may not.

        Args:
            clock: The clock to install. An object that only answers
                :meth:`~SupportsNow.now` is wrapped.

        Returns:
            What puts back the clock that was in force; calling it again does
            nothing.
        """
        resolved = _adapt(clock)
        # Marked inactive rather than reset, so the restore reaches the context
        # that installed it from wherever it is called.
        installed = _Installed(resolved, Clock._current.get())
        _ = Clock._current.set(installed)
        Clock._push(installed)

        def restore() -> None:
            if not installed.active:
                return
            installed.active = False
            Clock._pop(installed)

        return restore

    @classmethod
    @contextmanager
    def using(cls, clock: SupportsNow) -> Generator[ClockInterface]:
        """Install ``clock`` for the duration of a ``with`` block.

        The previous clock comes back on the way out, including when the
        block raises. For the context it runs in, scopes nest exactly. The
        process-wide fallback a thread started later reads is the innermost
        block still open, whichever context opened it: blocks in concurrent
        tasks may end in any order.

        Args:
            clock: The clock to install. An object that only answers
                :meth:`~SupportsNow.now` is wrapped.

        Yields:
            The clock as installed, which is ``clock`` itself unless it had
            to be wrapped.
        """
        resolved = _adapt(clock)
        token = Clock._current.set(resolved)
        entry = _Installed(resolved, None)
        Clock._push(entry)
        try:
            yield resolved
        finally:
            Clock._current.reset(token)
            entry.active = False
            Clock._pop(entry)

    @property
    def timezone(self) -> tzinfo | None:
        """The zone readings are pinned to, or ``None`` to follow the clock read."""
        return self._timezone

    @staticmethod
    def _push(entry: _Installed) -> None:
        """Make ``entry`` the innermost clock a context that installed nothing reads."""
        with Clock._active_lock:
            Clock._active.append(entry)

    @staticmethod
    def _pop(entry: _Installed) -> None:
        """Take ``entry`` away, wherever it sits: installs may end in any order."""
        with Clock._active_lock:
            Clock._active[:] = [kept for kept in Clock._active if kept is not entry]

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

    @override
    def __repr__(self) -> str:
        """Return a reading that names what is wrapped and any pinned zone."""
        pinned = f", {self._timezone!s}" if self._timezone is not None else ""

        return f"{type(self).__name__}({self._clock!r}{pinned})"


def _adapt(clock: SupportsNow) -> ClockInterface:
    """Return ``clock`` as a full contract, wrapping it only if it is not one."""
    return clock if isinstance(clock, ClockInterface) else Clock(clock)


@final
class _Installed:
    """A clock :meth:`Clock.install` put in force, and what was in force before it."""

    __slots__ = ("active", "clock", "previous")

    def __init__(self, clock: ClockInterface, previous: ClockInterface | _Installed | None) -> None:
        self.clock = clock
        self.previous = previous
        self.active = True
