"""The xtr-clock bundle: registers a :class:`~xtr_clock.clock.Clock` and pins it as global.

A container is asked for a :class:`~xtr_clock.clock_interface.ClockInterface`
and gets a :class:`~xtr_clock.clock.Clock` — over a
:class:`~xtr_clock.system_clock.SystemClock` in production, or a
:class:`~xtr_clock.mock_clock.MockClock` when
:attr:`~xtr_clock.bundle.clock_config.ClockConfig.mock` is on. On boot the
bundle also installs the container-built clock as
:meth:`~xtr_clock.clock.Clock.get`, so a helper reached through
:func:`~xtr_clock.now.now` sees the same instant as an injected class; on
shutdown it puts the previous clock back.
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import final

from typing_extensions import override
from xtr_dependency_injection import Bundle, ContainerBuilder, ServiceConfigurator, as_bundle

from xtr_clock.clock import Clock
from xtr_clock.clock_interface import ClockInterface
from xtr_clock.mock_clock import MockClock
from xtr_clock.system_clock import SystemClock

from .clock_config import ClockConfig

__all__ = ["ClockBundle"]


def _system_clock(config: ClockConfig) -> Clock:
    """Wrap a :class:`SystemClock` in a :class:`Clock` pinned to ``config.timezone``."""
    return Clock(SystemClock(), config.timezone)


def _mock_clock(config: ClockConfig) -> MockClock:
    """Freeze a :class:`MockClock` at ``config.frozen_at``."""
    return MockClock(config.frozen_at)


def _clock_over_mock(inner: MockClock, config: ClockConfig) -> Clock:
    """Wrap a :class:`MockClock` in a :class:`Clock` pinned to ``config.timezone``."""
    return Clock(inner, config.timezone)


@final
@as_bundle("clock", config=ClockConfig)
class ClockBundle(Bundle[ClockConfig]):
    """Provides a :class:`Clock` and keeps :meth:`Clock.get` in sync with it."""

    def __init__(self) -> None:
        """Prepare a scope for the boot-time :meth:`Clock.using` installation."""
        self._scope: ExitStack | None = None

    @override
    def load_extension(
        self,
        config: ClockConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register a :class:`Clock` factory and alias :class:`ClockInterface` onto it."""
        del builder
        if config.mock:
            _ = services.set(_mock_clock)
            _ = services.set(_clock_over_mock)
        else:
            _ = services.set(_system_clock)
        services.alias(ClockInterface, Clock)

    @override
    async def boot(self) -> None:
        """Install the container-built clock as :meth:`Clock.get` for the lifetime of the kernel."""
        container = self.container
        if container is None:  # pragma: no cover — the kernel sets this before boot.
            message = "ClockBundle.boot ran without a container"
            raise RuntimeError(message)
        clock = await container.get(ClockInterface)
        scope = ExitStack()
        _ = scope.enter_context(Clock.using(clock))
        self._scope = scope

    @override
    async def shutdown(self) -> None:
        """Restore the clock that was in force when :meth:`boot` ran."""
        scope = self._scope
        if scope is not None:
            self._scope = None
            scope.close()
