"""``cache:clear`` — reset every resettable service that was built."""

from __future__ import annotations

from xtr_console import ConsoleStyle, ExitCode, as_command
from xtr_dependency_injection import Injected, ServicesResetter

from fulltext import QueryLog, SearchEngineInterface

__all__ = ["clear_caches"]


@as_command("cache:clear")
async def clear_caches(
    io: ConsoleStyle,
    resetter: Injected[ServicesResetter],
    engine: Injected[SearchEngineInterface],
    queries: Injected[QueryLog],
) -> int:
    """Reset every resettable service that was built — what a worker does between messages.

    ``ServicesResetter`` calls ``reset`` on every built service implementing
    ``ResetInterface`` (the catalog cache, the logger factory) and the method named by every
    explicit ``kernel.reset`` tag (the query log's ``clear``). Services never built are not
    touched.

    Args:
        io: Where the command writes.
        resetter: The kernel's resetter.
        engine: The search engine, queried so the query log holds something.
        queries: The query log, to show the effect.
    """
    _ = engine.search("pragmatic")
    _ = engine.search("history")
    before = len(queries.queries())
    await resetter.reset()
    io.table(
        ["", "Before", "After"], [["logged queries", str(before), str(len(queries.queries()))]]
    )
    io.success("Every built resettable service was reset.")
    return ExitCode.SUCCESS
