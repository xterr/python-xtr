"""A worker entry point: ``python -m bookshop.worker [transport ...]``.

The same as ``bookshop messenger:consume``, without the console: boot, build a worker over
the named transports, run it until it returns or SIGTERM stops it, shut down. In dev the
transports are in-memory, so a fresh process has nothing to drain and returns at once; in
prod (``APP_ENV=prod``) it consumes RabbitMQ until stopped.
"""

from __future__ import annotations

import asyncio
import signal
import sys

from xtr_messenger import WorkerFactory

from bookshop.kernel import kernel, load_environment

__all__ = ["consume", "main"]


async def consume(transports: list[str]) -> None:
    """Boot, consume ``transports``, shut down."""
    async with await kernel.boot() as booted:
        workers = await booted.container.get(WorkerFactory)
        worker = workers.worker(transports)
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, worker.stop)
        await worker.run()


def main() -> None:
    """Consume the transports named on the command line — ``jobs`` by default."""
    load_environment()
    asyncio.run(consume(sys.argv[1:] or ["jobs"]))


if __name__ == "__main__":
    main()
