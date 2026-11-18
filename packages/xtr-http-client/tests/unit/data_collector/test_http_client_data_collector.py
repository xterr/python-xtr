from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, cast

import anyio
import pytest
from anyio.lowlevel import checkpoint
from xtr_http_kernel.data_collector import (
    LateDataCollectorInterface,
    ProfiledRequest,
    TracingDataCollectorInterface,
)
from xtr_http_message import ServerRequest

from xtr_http_client import MockHttpClient, MockResponse, TraceableHttpClient
from xtr_http_client.data_collector import HttpClientDataCollector
from xtr_http_client.data_collector._masking import MASK

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import RequestOptions

    from xtr_http_client import TracedRequest

pytestmark = pytest.mark.anyio

_URL = "https://api.test/orders"
_PROFILED = ProfiledRequest(ServerRequest("GET", "/"), 200, {}, {})


def _traced(
    options: RequestOptions | None = None,
    info: Mapping[str, object] | None = None,
    content: bytes | bool | None = None,
) -> TracedRequest:
    return {
        "method": "POST",
        "url": _URL,
        "options": options if options is not None else {},
        "info": info if info is not None else {},
        "content": content,
    }


def _requests(data: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", data["requests"])


def _late(collector: HttpClientDataCollector) -> dict[str, object]:
    return collector.late_collect(collector.collect(_PROFILED), _PROFILED)


def test_it_is_named_after_the_panel() -> None:
    assert HttpClientDataCollector().name == "http_client"


def test_it_traces_the_request_and_settles_late() -> None:
    collector = HttpClientDataCollector()

    assert isinstance(collector, TracingDataCollectorInterface)
    assert isinstance(collector, LateDataCollectorInterface)


def test_nothing_is_kept_outside_a_profiled_request() -> None:
    collector = HttpClientDataCollector()

    collector.record("http_client", _traced())

    assert not collector.is_recording()
    assert _late(collector) == {"requests": [], "count": 0, "errors": 0, "duration_ms": 0}


def test_a_request_is_kept_with_its_answer() -> None:
    collector = HttpClientDataCollector()
    collector.begin_request()
    info = {
        "http_code": 201,
        "total_time": 0.25,
        "error": None,
        "url": "https://api.test/orders?page=1",
        "response_headers": ["HTTP/1.1 201 Created", "Content-Type: application/json"],
    }

    collector.record("http_client_github", _traced({"json": {"id": 7}}, info, b"{}"))

    assert _requests(_late(collector)) == [
        {
            "client": "http_client_github",
            "method": "POST",
            "url": "https://api.test/orders?page=1",
            "status": 201,
            "duration_ms": 250.0,
            "error": None,
            "request_headers": [],
            "request_body": {
                "kind": "mapping",
                "type": "dict",
                "items": [
                    [
                        {"kind": "str", "type": "str", "value": "id", "truncated": 0},
                        {"kind": "scalar", "type": "int", "value": 7},
                    ]
                ],
                "truncated": 0,
            },
            "response_headers": ["HTTP/1.1 201 Created", "Content-Type: application/json"],
            "response_size": 2,
            "content_traced": True,
        }
    ]


def test_a_request_still_unanswered_is_kept_by_what_it_asked_for() -> None:
    collector = HttpClientDataCollector()
    collector.begin_request()

    collector.record("http_client", _traced())

    [entry] = _requests(collector.collect(_PROFILED))
    assert entry["url"] == _URL
    assert entry["status"] is None
    assert entry["duration_ms"] is None
    assert entry["response_headers"] == []
    assert entry["response_size"] is None
    assert entry["request_body"] is None


def test_credentials_are_masked() -> None:
    collector = HttpClientDataCollector()
    collector.begin_request()
    options: RequestOptions = {
        "headers": {"Authorization": "Bearer t", "Accept": ["a/b", "c/d"]},
        "body": {"user": "ann", "password": "pw"},
    }
    info = {"response_headers": ["HTTP/1.1 200 OK", "Set-Cookie: s=1", 7]}

    collector.record("http_client", _traced(options, info))

    [entry] = _requests(_late(collector))
    assert entry["request_headers"] == [f"Authorization: {MASK}", "Accept: a/b", "Accept: c/d"]
    assert entry["response_headers"] == ["HTTP/1.1 200 OK", f"Set-Cookie: {MASK}"]
    body = cast("dict[str, list[list[dict[str, object]]]]", entry["request_body"])
    assert [value["value"] for _, value in body["items"]] == ["ann", MASK]


def test_a_request_whose_bodies_are_not_kept_shows_none() -> None:
    collector = HttpClientDataCollector()
    collector.begin_request()

    collector.record("http_client", _traced({"json": {"id": 7}}, content=False))

    [entry] = _requests(_late(collector))
    assert entry["request_body"] is None
    assert entry["response_size"] is None
    assert entry["content_traced"] is False


def test_response_headers_that_are_not_lines_are_left_out() -> None:
    collector = HttpClientDataCollector()
    collector.begin_request()

    collector.record("http_client", _traced(info={"response_headers": "Accept: a/b"}))

    assert _requests(_late(collector))[0]["response_headers"] == []


def test_failures_and_known_durations_are_totalled() -> None:
    collector = HttpClientDataCollector()
    collector.begin_request()

    collector.record("http_client", _traced(info={"http_code": 200, "total_time": 0.5}))
    collector.record("http_client", _traced(info={"http_code": 404, "total_time": 1}))
    collector.record("http_client", _traced(info={"error": "Connection refused."}))
    collector.record("http_client", _traced(info={"http_code": True, "total_time": False}))

    data = _late(collector)
    assert data["count"] == 4
    assert data["errors"] == 2
    assert data["duration_ms"] == 1500.0
    assert _requests(data)[2]["error"] == "Connection refused."
    assert _requests(data)[3]["status"] is None


async def test_two_requests_profiled_at_once_each_see_their_own() -> None:
    collector = HttpClientDataCollector()
    seen: dict[str, list[object]] = {}

    async def serve(client: str) -> None:
        collector.begin_request()
        collector.record(client, _traced())
        await checkpoint()
        seen[client] = [entry["client"] for entry in _requests(_late(collector))]

    async with anyio.create_task_group() as group:
        _ = group.start_soon(serve, "first")
        _ = group.start_soon(serve, "second")

    assert seen == {"first": ["first"], "second": ["second"]}


async def test_a_traced_client_hands_it_what_it_sends_and_what_came_back() -> None:
    collector = HttpClientDataCollector()
    collector.begin_request()
    answer = MockResponse(b"hello", {"http_code": 503})
    client = TraceableHttpClient(
        MockHttpClient(answer), recorder=partial(collector.record, "http_client")
    )

    async with await client.request("GET", _URL) as response:
        _ = await response.get_content(throw=False)

    [entry] = _requests(_late(collector))
    assert entry["method"] == "GET"
    assert entry["status"] == 503
    assert entry["response_size"] == 5
    assert isinstance(entry["duration_ms"], float)
    assert _late(collector)["errors"] == 1
