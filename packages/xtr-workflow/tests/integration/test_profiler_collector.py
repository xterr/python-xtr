"""End-to-end: with the http kernel's profiler on in debug mode, workflow calls reach its panel."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.data_collector import ProfiledRequest
from xtr_http_kernel.profiler import Profiler
from xtr_http_message import ServerRequest

from tests.fixtures.app_workflow.subjects import Article
from xtr_workflow import WorkflowInterface
from xtr_workflow.bundle import WorkflowBundle
from xtr_workflow.data_collector import WorkflowDataCollector

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_APP = "tests.fixtures.app_workflow"
_PROFILER_ON = "tests.fixtures.profiler_on"
_PROFILED = ProfiledRequest(ServerRequest("GET", "/"), 200, {}, {})


@pytest.fixture(autouse=True)
def _profiles_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))


def _kernel(*resources: str, debug: bool = True) -> Kernel:
    return Kernel(
        _APP,
        env="test",
        debug=debug,
        bundles={WorkflowBundle: {"all": True}, HttpKernelBundle: {"all": True}},
        resources=(_APP, *resources),
    )


async def test_with_the_profiler_on_in_debug_mode_the_panel_is_registered() -> None:
    async with await _kernel(_PROFILER_ON).boot() as booted:
        profiler = await booted.container.get(Profiler)

        assert profiler.has("workflow")
        assert profiler.get("workflow") is await booted.container.get(WorkflowDataCollector)


async def test_the_panel_shows_every_defined_workflow() -> None:
    async with await _kernel(_PROFILER_ON).boot() as booted:
        collector = await booted.container.get(WorkflowDataCollector)

        data = collector.collect(_PROFILED)

    workflows = cast("list[dict[str, object]]", data["workflows"])
    assert [workflow["name"] for workflow in workflows] == [
        "article",
        "pull_request",
        "service_marking_store_workflow",
        "by_strategy",
        "injected_only",
    ]
    assert workflows[:2] == [
        {
            "name": "article",
            "type": "workflow",
            "supports": ["tests.fixtures.app_workflow.subjects.Article"],
        },
        {
            "name": "pull_request",
            "type": "state_machine",
            "supports": ["tests.fixtures.app_workflow.subjects.PullRequest"],
        },
    ]


async def test_the_calls_of_a_profiled_request_are_collected() -> None:
    async with await _kernel(_PROFILER_ON).boot() as booted:
        collector = await booted.container.get(WorkflowDataCollector)
        article = await booted.container.get(WorkflowInterface, "article")
        subject = Article()

        collector.begin_request()
        _ = await article.can(subject, "publish")
        _ = await article.apply(subject, "request_review")

        data = collector.late_collect(collector.collect(_PROFILED), _PROFILED)

    calls = cast("list[dict[str, object]]", data["calls"])
    assert data["counts"] == {"calls": 2, "applied": 1, "blocked": 1}
    assert [(call["workflow"], call["method"], call["transition"]) for call in calls] == [
        ("article", "can", "publish"),
        ("article", "apply", "request_review"),
    ]
    assert calls[0]["result"] is False
    assert (calls[1]["previous_marking"], calls[1]["marking"]) == (
        ["draft"],
        ["wait_for_journalist", "wait_for_spellchecker"],
    )
    assert calls[1]["subject"] == "tests.fixtures.app_workflow.subjects.Article"


async def test_with_the_profiler_off_the_panel_is_not_registered() -> None:
    async with await _kernel().boot() as booted:
        assert not booted.container.has(WorkflowDataCollector)


async def test_outside_debug_mode_the_panel_is_not_registered() -> None:
    async with await _kernel(_PROFILER_ON, debug=False).boot() as booted:
        assert booted.container.has(Profiler)
        assert not booted.container.has(WorkflowDataCollector)
