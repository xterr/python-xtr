"""``orders:reindex`` — a pydantic message, optionally forced onto a transport."""

from __future__ import annotations

from xtr_console import ConsoleStyle, ExitCode, as_command
from xtr_dependency_injection import Injected
from xtr_messenger import MessageBusInterface, TransportNamesStamp, WorkerFactory

from bookshop.message.reindex_catalog import ReindexCatalog
from bookshop.service.describe_envelope import describe_envelope

__all__ = ["reindex_catalog"]


@as_command("orders:reindex")
async def reindex_catalog(
    io: ConsoleStyle,
    reason: str = "manual",
    *,
    via: str | None = None,
    bus: Injected[MessageBusInterface],
    workers: Injected[WorkerFactory],
) -> int:
    """Ask for a reindex — a pydantic message — optionally forcing its transport.

    Args:
        io: Where the command writes.
        reason: Why (three characters or more: the model validates it).
        via: A transport to send it through instead of the one it declares; a
            ``TransportNamesStamp`` on the envelope beats the routing table.
        bus: The bus.
        workers: Builds the worker that handles it.
    """
    stamps = [TransportNamesStamp((via,))] if via else []
    envelope = await bus.dispatch(ReindexCatalog(reason=reason), *stamps)
    describe_envelope(io, envelope)
    target = via or "jobs"
    if target != "sync":  # sync:// handled it during the dispatch: nothing is queued there.
        await workers.worker([target]).run()
    io.success("Catalog reindexed.")
    return ExitCode.SUCCESS
