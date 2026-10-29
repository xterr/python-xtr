"""A boot hook adding the console application's own hooks, around every command it runs."""

from __future__ import annotations

from xtr_console import Application, ConsoleStyle, Verbosity
from xtr_dependency_injection import Injected, on_boot

__all__ = ["wire_console_hooks"]


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
