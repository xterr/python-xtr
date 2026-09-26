"""Code run as the kernel boots and shuts down: ``@on_boot`` and ``@on_shutdown``.

::

    boot()      bundle.boot() in bundle order -> @on_boot, highest priority first
    shutdown()  @on_shutdown, highest priority first -> bundle.shutdown() in reverse
                -> the container closes (every generator factory's cleanup runs)

Hooks are injected — ``Injected[...]``, ``Autowire(...)``, ``Target(...)`` — and may be sync
or async. A *sync* hook can only receive services the container builds synchronously: a
service built by an async factory — or depending on one, like every logger (the logger
factory is an async generator) and the console ``Application`` — needs an ``async def`` hook.
A failing boot hook shuts down what already booted, in reverse, and propagates;
``@on_shutdown`` hooks run only after a boot that succeeded.
"""

from __future__ import annotations

from typing import Annotated, cast

from xtr_console import Application, ConsoleStyle, Verbosity
from xtr_dependency_injection import (
    Autowire,
    Injected,
    KernelInterface,
    ServicesResetter,
    Target,
    on_boot,
    on_shutdown,
    when,
)
from xtr_logging_contracts import LoggerInterface
from xtr_service_contracts import ContainerInterface

from bookshop.health import STARTUP_CHECK_TAG, StartupCheck

__all__ = [
    "announce_boot",
    "describe_development_environment",
    "goodbye",
    "reset_between_units_of_work",
    "run_startup_checks",
    "wire_console_hooks",
]


@on_boot(priority=100)
def announce_boot(
    kernel: Injected[KernelInterface],
    logger: Injected[LoggerInterface],
    shop: Annotated[str, Autowire(param="shop.name")],
) -> None:
    """Runs first (highest priority): a sync hook, with a parameter holding an ``env()``."""
    logger.info(
        "{shop} booting in {env}",
        {"shop": shop, "env": kernel.environment, "bundles": list(kernel.bundles)},
    )


@on_boot
async def run_startup_checks(
    kernel: Injected[KernelInterface],
    container: Injected[ContainerInterface],
    logger: Annotated[LoggerInterface, Target("app")],
) -> None:
    """Run every startup check, in the order the kernel emitted them.

    The kernel's report lists definitions in emission order — the order ``priority``,
    ``before`` and ``after`` decided — with their tags; this hook reads it back.
    """
    for definition in kernel.report.definitions:
        if STARTUP_CHECK_TAG not in definition.tags:
            continue
        provided, qualifier = definition.key
        check = cast("StartupCheck", await container.get(provided, qualifier))
        outcome = await check.run()
        logger.info(
            "startup check {check}: {outcome}", {"check": provided.__name__, "outcome": outcome}
        )


@on_boot
@when("dev")
@when("test")
def describe_development_environment(
    logger: Injected[LoggerInterface],
    project_dir: Annotated[str, Autowire(param="kernel.project_dir")],
) -> None:
    """Only in dev and test — ``@when`` repeated widens the set, like ``@when("dev", "test")``."""
    logger.debug("project directory: {dir}", {"dir": project_dir})


@on_boot(priority=-10)
async def wire_console_hooks(application: Injected[Application]) -> None:
    """Add the console application's own hooks, around every command it runs.

    ``on_configure`` receives the command's style once its global options are applied;
    ``on_startup`` / ``on_shutdown`` run on the command's event loop, sync or async, and
    every shutdown hook runs even when the command raised.
    """

    def remember_verbosity(io: ConsoleStyle) -> None:
        io.text(f"verbosity: {io.verbosity.name}", verbosity=Verbosity.DEBUG)

    async def before_command() -> None:
        return None

    def after_command() -> None:
        return None

    application.on_configure(remember_verbosity)
    application.on_startup(before_command)
    application.on_shutdown(after_command)


@on_shutdown(priority=10)
async def reset_between_units_of_work(resetter: Injected[ServicesResetter]) -> None:
    """Reset every built resettable service — what a worker does after each message."""
    await resetter.reset()


@on_shutdown
async def goodbye(logger: Injected[LoggerInterface], kernel: Injected[KernelInterface]) -> None:
    """Runs after the higher-priority shutdown hook, before the bundles shut down."""
    logger.info("{name} shutting down", {"name": kernel.name})
