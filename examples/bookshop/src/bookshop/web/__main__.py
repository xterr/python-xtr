"""The web entry point: ``uv run bookshop-web`` or ``python -m bookshop.web``.

Stop it with Ctrl-C or SIGTERM: the server stops accepting, then the lifespan shuts the
kernel down — ``@on_shutdown`` hooks, bundles in reverse, the container's cleanup.
"""

from __future__ import annotations

import asyncio
import signal

from bookshop.kernel import kernel, load_environment

from .server import HttpServer


async def serve() -> None:
    """Build, boot through the lifespan, serve until a signal, shut down."""
    compiled = kernel.build()  # the container exists before the server does
    async with compiled.lifespan(None):  # boot on enter, shutdown on exit
        server = await compiled.container.get(HttpServer)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signum, stop.set)
        await server.serve(stop)


def main() -> None:
    """Load the environment, then serve."""
    load_environment()
    asyncio.run(serve())


if __name__ == "__main__":
    main()
