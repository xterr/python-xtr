"""End-to-end: with the http kernel's profiler on, the clients' requests reach its panel."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.data_collector import ProfiledRequest
from xtr_http_kernel.profiler import Profiler
from xtr_http_message import ServerRequest

from xtr_http_client import JsonMockResponse, MockHttpClient, MockResponse
from xtr_http_client.bundle import HttpClientBundle
from xtr_http_client.data_collector import HttpClientDataCollector

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_PROFILER_ON = "tests.fixtures.profiler_on"
_PROFILED = ProfiledRequest(ServerRequest("GET", "/"), 200, {}, {})


@pytest.fixture(autouse=True)
def _profiles_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))


def _kernel(*resources: str) -> Kernel:
    return Kernel(
        HttpClientBundle.__module__,
        env="test",
        bundles={HttpClientBundle: {"all": True}, HttpKernelBundle: {"all": True}},
        resources=resources,
    )


async def test_with_the_profiler_on_the_panel_is_registered() -> None:
    async with await _kernel(_PROFILER_ON).boot() as booted:
        profiler = await booted.container.get(Profiler)

        assert profiler.has("http_client")
        assert profiler.get("http_client") is await booted.container.get(HttpClientDataCollector)


async def test_the_requests_of_a_profiled_request_are_collected() -> None:
    async with await _kernel(_PROFILER_ON).boot() as booted:
        collector = await booted.container.get(HttpClientDataCollector)
        (await booted.container.get(MockHttpClient)).set_response_factory(
            [
                JsonMockResponse({"id": 7}, {"http_code": 201}),
                MockResponse(b"gone", {"http_code": 404}),
            ]
        )
        default = await booted.container.get(HttpClientInterface)
        github = await booted.container.get(HttpClientInterface, "github")

        collector.begin_request()
        async with await default.request(
            "POST", "https://api.test/orders", json={"id": 7, "token": "t"}
        ) as response:
            body = await response.get_content()
        async with await github.request("GET", "repos") as response:
            _ = await response.get_content(throw=False)

        data = collector.late_collect(collector.collect(_PROFILED), _PROFILED)

    requests = cast("list[dict[str, object]]", data["requests"])
    assert data["count"] == 2
    assert data["errors"] == 1
    assert [entry["client"] for entry in requests] == ["http_client", "http_client_github"]
    assert [entry["status"] for entry in requests] == [201, 404]
    assert requests[1]["url"] == "https://api.github.test/repos"
    assert requests[0]["response_size"] == len(body)
    assert "******" in str(requests[0]["request_body"])


async def test_with_the_profiler_off_the_panel_is_not_registered() -> None:
    async with await _kernel().boot() as booted:
        assert not booted.container.has(HttpClientDataCollector)
        assert not booted.container.has(Profiler)
