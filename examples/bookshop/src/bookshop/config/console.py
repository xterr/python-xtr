"""The console application: every ``ConsoleConfig`` field."""

from __future__ import annotations

from dataclasses import replace
from importlib.metadata import version

from xtr_console.bundle import ConsoleConfig
from xtr_dependency_injection import configure, when

__all__ = ["console", "console_in_test"]


@configure
def console() -> ConsoleConfig:
    """Name, version (enables ``--version``), description, and error reporting."""
    return ConsoleConfig(
        name="bookshop",  # None would use the kernel's name
        version=version("bookshop"),  # None disables --version / -V
        description="Run the bookshop: catalog, orders, search, diagnostics.",
        catch_exceptions=True,  # report an escaping exception and exit 1
    )


@configure(priority=10)
@when("test")
def console_in_test(config: ConsoleConfig) -> ConsoleConfig:
    """In test, let an exception escaping a command propagate — a test wants the traceback."""
    return replace(config, catch_exceptions=False)
