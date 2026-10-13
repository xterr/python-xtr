"""A disposable HTTP server a client implementation can be tested against."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, ClassVar, Final, final

from ._fixture_request import read_request
from ._fixture_routes import respond

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Self

__all__ = ["TestHttpServer"]

_HOST: Final = "127.0.0.1"
_PORT: Final = 8057


@final
class TestHttpServer:
    """The server the conformance suite points a client at.

    It runs on an event loop of its own, in a background thread, because the client under test
    owns the loop its own code runs on: a client that stops pumping its loop — which is exactly
    what a timeout test provokes — must not stop the server that is meant to keep answering it.

    ``start()`` returns once the port is listening, and both ``start()`` and ``stop()`` may be
    called again at any point, so one instance can live for a whole test session::

        @pytest.fixture(scope="session")
        def http_server() -> Iterator[TestHttpServer]:
            with TestHttpServer() as server:
                yield server

    What each route answers is described in ``_fixture_routes``; what the echoing ones report
    about the request is described in ``_fixture_request``.
    """

    __test__: ClassVar[bool] = False  # a library class, not a pytest test case

    __slots__ = ("_failure", "_host", "_loop", "_port", "_ready", "_stop", "_thread")

    def __init__(self, host: str = _HOST, port: int = _PORT) -> None:
        """Bind nothing yet: the socket is opened by :meth:`start`."""
        self._host = host
        self._port = port
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._failure: BaseException | None = None

    @property
    def host(self) -> str:
        """The address the server listens on."""
        return self._host

    @property
    def port(self) -> int:
        """The port the server listens on."""
        return self._port

    @property
    def base_uri(self) -> str:
        """The origin a client should send its requests to."""
        return f"http://{self._host}:{self._port}"

    def start(self) -> None:
        """Listen, and return once the port accepts connections.

        Starting an already-running server does nothing, so a fixture may start it defensively.
        Whatever stopped the thread from listening — a port already taken, most often — is
        raised here rather than left to make every later request fail obscurely.
        """
        if self._thread is not None:
            return
        self._failure = None
        self._ready.clear()
        thread = threading.Thread(target=self._run, name="xtr-fixture-http-server", daemon=True)
        self._thread = thread
        thread.start()
        _ = self._ready.wait()
        failure = self._failure
        if failure is not None:
            self._thread = None
            self._failure = None
            raise failure

    def stop(self) -> None:
        """Close the port and everything still connected to it.

        Stopping a server that is not running does nothing, and a stopped server can be started
        again; a route still writing when this is called is cut off rather than waited for.
        """
        thread, loop, stop = self._thread, self._loop, self._stop
        self._thread = None
        self._loop = None
        self._stop = None
        if thread is None:
            return
        if loop is not None and stop is not None:
            _ = loop.call_soon_threadsafe(stop.set)
        thread.join()

    def __enter__(self) -> Self:
        """Start, for a test that wants the server for the length of a block."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop, whatever the block did."""
        del exc, exc_type, traceback
        self.stop()

    def _run(self) -> None:
        """The background thread: one event loop, used for nothing else."""
        try:
            asyncio.run(self._serve())
        except BaseException as failure:  # noqa: BLE001 - re-raised by start()
            self._failure = failure
        finally:
            self._ready.set()

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        self._stop = stop
        server = await asyncio.start_server(self._handle, self._host, self._port)
        self._ready.set()
        try:
            _ = await stop.wait()
        finally:
            # Order matters: everything connected goes before the listener does. A connection
            # that attaches after a server has been closed makes the standard library wake
            # waiters it already dropped, and the socket cleanup that was underneath dies with
            # it — leaving the socket open. Nothing can attach once no accept is in flight.
            await _end_everything_still_serving()
            server.close()
            await server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Answer one request and close, as every response promises in its headers."""
        try:
            request = await read_request(reader, writer, self._host)
            if request is not None:
                await respond(request, writer)
            writer.close()
            await writer.wait_closed()
        except (OSError, EOFError):
            pass  # the client hung up mid-exchange, which several routes exist to provoke
        finally:
            # However the exchange ended — cut short by a cancelled route included — the socket
            # may not outlive the handler, or the loop is closed with it still open. Aborting
            # an already-closed transport does nothing, so the orderly path above still wins.
            writer.transport.abort()


async def _end_everything_still_serving() -> None:
    """Cancel every other task on this loop, wait for it, and let its socket close.

    This is what ``asyncio.run`` would do on the way out, done here instead while the loop can
    still run, because the runner drops what it cancels with its sockets still open.

    The two turns of the loop around the cancelling are both load-bearing. Before: a connection
    accepted in the same breath as the shutdown has a task that has not run at all yet, holding
    the accepted socket and nothing that could close it; one turn lets it reach the transport,
    which cancelling then closes. After: losing a connection is a callback, and the sockets the
    cancelled tasks just abandoned are still waiting for it.
    """
    await asyncio.sleep(0)
    current = asyncio.current_task()
    serving = [task for task in asyncio.all_tasks() if task is not current]
    for task in serving:
        _ = task.cancel()
    _ = await asyncio.gather(*serving, return_exceptions=True)
    await asyncio.sleep(0)
