"""A minimal HTTP/1.1 server on ``asyncio.start_server``: one request per connection."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Annotated, Final, cast, final
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

from xtr_dependency_injection import Autowire, ServicesResetter, Target, as_service, bind_callable
from xtr_logging import bound_context
from xtr_logging_contracts import EXCEPTION_KEY, LoggerInterface
from xtr_service_contracts import ContainerInterface

from bookshop.observability.logging_services import REQUEST_ID
from bookshop.ordering.errors import OrderRefusedError, UnknownBookError

from .http import HttpError, Request, Response
from .routes import ROUTES, Route

__all__ = ["HttpServer"]

_MAX_HEADERS: Final = 100
Endpoint = Callable[[Request], Awaitable[object]]


@final
@as_service
class HttpServer:
    """Serves :data:`~bookshop.web.routes.ROUTES` from the container.

    Built by the container like any service: its address comes from the environment, its
    access log is the ``http`` channel (which the logging config sends to a rotating JSON file
    and to standard output).
    """

    def __init__(
        self,
        container: ContainerInterface,
        resetter: ServicesResetter,
        logger: Annotated[LoggerInterface, Target("http")],
        host: Annotated[str, Autowire(env="WEB_HOST")],
        port: Annotated[int, Autowire(env="int:WEB_PORT")],
    ) -> None:
        """Bind every route now: a route the container cannot serve fails here, at startup."""
        self._resetter = resetter
        self._logger = logger
        self.host = host
        self.port = port
        self._routes: list[tuple[Route, Endpoint]] = [
            (route, cast("Endpoint", bind_callable(container, route.endpoint, per_call_scope=True)))
            for route in ROUTES
        ]

    async def serve(self, stop: asyncio.Event) -> None:
        """Accept connections until ``stop`` is set."""
        server = await asyncio.start_server(self._connection, self.host, self.port)
        self._logger.notice(
            "listening on http://{host}:{port}", {"host": self.host, "port": self.port}
        )
        async with server:
            _ = await stop.wait()
        self._logger.notice("stopped listening")

    async def _connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request_id = uuid4().hex[:8]
        token = REQUEST_ID.set(request_id)
        started = time.perf_counter()
        try:
            with bound_context({"request_id": request_id}):
                request = await _read(reader)
                response = await self._dispatch(request)
                self._logger.info(
                    "{method} {path} {status}",
                    {
                        "method": request.method,
                        "path": request.path,
                        "status": response.status.value,
                        "ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
            _write(writer, response, request_id)
            await writer.drain()
        finally:
            REQUEST_ID.reset(token)
            writer.close()
            # A unit of work ended: reset what must not leak into the next one.
            await self._resetter.reset()

    async def _dispatch(self, request: Request) -> Response:
        allowed = False
        for route, endpoint in self._routes:
            captured = route.match(request.method, request.path)
            if captured is None:
                continue
            allowed = True
            if route.method != request.method:
                continue
            routed = Request(
                request.method, request.path, request.query, request.headers, request.body, captured
            )
            return await self._call(endpoint, routed)
        status = HTTPStatus.METHOD_NOT_ALLOWED if allowed else HTTPStatus.NOT_FOUND
        return Response.json({"error": status.phrase}, status)

    async def _call(self, endpoint: Endpoint, request: Request) -> Response:
        try:
            return cast("Response", await endpoint(request))
        except HttpError as error:
            return Response.json({"error": error.detail}, error.status)
        except UnknownBookError as error:
            return Response.json({"error": str(error)}, HTTPStatus.NOT_FOUND)
        except OrderRefusedError as error:
            return Response.json({"error": str(error)}, HTTPStatus.UNPROCESSABLE_ENTITY)
        except Exception as error:  # noqa: BLE001 — a request never takes the server down.
            self._logger.error("{path} failed", {"path": request.path, EXCEPTION_KEY: error})
            return Response.json({"error": "internal error"}, HTTPStatus.INTERNAL_SERVER_ERROR)


async def _read(reader: asyncio.StreamReader) -> Request:
    """Read one request: the request line, the headers, and a ``Content-Length`` body."""
    method, target, _ = (await reader.readline()).decode("latin-1").split(" ", 2)
    headers: dict[str, str] = {}
    for _ in range(_MAX_HEADERS):
        line = (await reader.readline()).decode("latin-1").strip()
        if not line:
            break
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    body = await reader.readexactly(length) if length else b""
    url = urlsplit(target)
    return Request(method.upper(), url.path, dict(parse_qsl(url.query)), headers, body)


def _write(writer: asyncio.StreamWriter, response: Response, request_id: str) -> None:
    head = (
        f"HTTP/1.1 {response.status.value} {response.status.phrase}\r\n"
        f"Content-Type: {response.content_type}\r\n"
        f"Content-Length: {len(response.body)}\r\n"
        f"X-Request-Id: {request_id}\r\n"
        "Connection: close\r\n\r\n"
    )
    writer.write(head.encode("latin-1") + response.body)
