"""Unit tests for the middleware factory the bundle contributes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from starlette.responses import PlainTextResponse
from xtr_event_dispatcher import EventDispatcher
from xtr_http_message import HttpFactory

from xtr_http_kernel import RequestEvent, RequestLifecycleMiddleware
from xtr_http_kernel.bridge import HttpMessageFactory, ResponseFactory
from xtr_http_kernel.bundle.request_lifecycle_middleware_factory import (
    RequestLifecycleMiddlewareFactory,
)

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send


def _messages() -> HttpMessageFactory:
    one = HttpFactory()
    return HttpMessageFactory(one, one, one, ResponseFactory(), one)


async def _app(scope: object, receive: object, send: object) -> None:
    del scope, receive, send


def test_it_carries_no_priority_of_its_own() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages())

    assert not hasattr(factory, "priority")


def test_it_wraps_the_app_in_the_lifecycle_middleware() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages())

    wrapped = factory(_app)

    assert isinstance(wrapped, RequestLifecycleMiddleware)


async def _answered(app: object, host: bytes) -> list[Message]:
    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"host", host)],
        "server": ("127.0.0.1", 8000),
    }
    await cast("ASGIApp", app)(scope, receive, send)
    return sent


async def _hello(scope: Scope, receive: Receive, send: Send) -> None:
    await PlainTextResponse("hello")(scope, receive, send)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("host", "status"),
    [(b"app.test", 200), (b"api.app.test:8000", 200), (b"evil.test", 400), (b"a b", 400)],
)
async def test_a_host_outside_the_trusted_hosts_gets_400_before_the_lifecycle(
    host: bytes, status: int
) -> None:
    dispatcher = EventDispatcher()
    requests: list[RequestEvent] = []
    dispatcher.add_listener(RequestEvent, requests.append)
    factory = RequestLifecycleMiddlewareFactory(
        dispatcher, _messages(), trusted_hosts=("app.test", "*.app.test")
    )

    sent = await _answered(factory(_hello), host)

    assert sent[0]["status"] == status
    assert len(requests) == (1 if status == 200 else 0)


@pytest.mark.anyio
async def test_no_trusted_hosts_lets_any_host_through() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages())

    sent = await _answered(factory(_hello), b"anything.test")

    assert sent[0]["status"] == 200
