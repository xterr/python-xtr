"""``ping`` — ``@as_command`` bare: named after the function; a *sync* command."""

from __future__ import annotations

from xtr_console import ConsoleStyle, ExitCode, Verbosity, as_command

__all__ = ["ping"]


@as_command
def ping(io: ConsoleStyle) -> int:
    """Answer pong — a sync command runs on the application's event loop too."""
    io.text("pong", verbosity=Verbosity.QUIET)
    return ExitCode.SUCCESS
