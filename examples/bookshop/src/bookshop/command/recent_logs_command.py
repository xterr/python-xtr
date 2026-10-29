"""``logs:recent`` — the last records the in-memory handler kept."""

from __future__ import annotations

from xtr_console import ConsoleStyle, ExitCode, Verbosity, as_command, escape
from xtr_dependency_injection import Injected
from xtr_logging import LoggerFactory, TestHandler

__all__ = ["recent_logs"]


@as_command("logs:recent")
async def recent_logs(
    io: ConsoleStyle,
    factory: Injected[LoggerFactory],
    *,
    count: int = 10,
) -> int:
    """Print the last records the in-memory handler kept.

    Args:
        io: Where the command writes.
        factory: The logger factory — any configured handler is reachable by name.
        count: How many records.
    """
    handler = factory.handler("memory")
    if not isinstance(handler, TestHandler):
        io.error("The memory handler is not a TestHandler.")
        return ExitCode.FAILURE
    io.text(f"channels: {', '.join(factory.channels)}", verbosity=Verbosity.VERBOSE)
    io.table(
        ["Channel", "Level", "Message"],
        [
            [record.channel, record.level.name, escape(record.message)]
            for record in handler.records[-count:]
        ],
    )
    return ExitCode.SUCCESS
