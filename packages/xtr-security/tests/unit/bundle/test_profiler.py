"""The security panel is registered, and reported to, exactly while requests are profiled."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_http_kernel.data_collector import DataCollectorTemplates
from xtr_http_kernel.profiler import Profiler
from xtr_security_core import TraceableAccessDecisionManager

from tests.fixtures.security_app.bundles import BUNDLES
from xtr_security.data_collector import SecurityDataCollector

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_APP = "tests.fixtures.security_app"
_PROFILER_ON = "tests.fixtures.profiler_on"


@pytest.fixture(autouse=True)
def _profiles_under_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))


def _kernel(*resources: str, debug: bool = True) -> Kernel:
    return Kernel(
        _APP,
        env="test",
        debug=debug,
        bundles=BUNDLES,
        resources=(_APP, *resources),
        concurrent_scoped_access=True,
    )


async def test_the_panel_is_shown_with_its_template_after_the_router() -> None:
    async with await _kernel(_PROFILER_ON).boot() as booted:
        templates = await booted.container.get(DataCollectorTemplates)

    names = [name for name, _ in templates.entries]
    assert templates.template_of("security") == "@xtr_security/collector/security.html.j2"
    # Priority 270: after the router's 285, ahead of the config's -255.
    assert names.index("router") < names.index("security") < names.index("config")


async def test_the_profiler_holds_the_panel() -> None:
    async with await _kernel(_PROFILER_ON).boot() as booted:
        profiler = await booted.container.get(Profiler)

        assert isinstance(profiler.get("security"), SecurityDataCollector)


async def test_in_debug_mode_the_panel_says_both_are_traced() -> None:
    async with await _kernel(_PROFILER_ON).boot() as booted:
        collector = await booted.container.get(SecurityDataCollector)

    assert collector._votes_traced is True
    assert collector._authenticators_traced is True


async def test_outside_debug_mode_the_panel_says_neither_is_traced() -> None:
    async with await _kernel(_PROFILER_ON, debug=False).boot() as booted:
        collector = await booted.container.get(SecurityDataCollector)

    assert collector._votes_traced is False
    assert collector._authenticators_traced is False


async def test_the_traced_decision_manager_reports_to_the_panel() -> None:
    async with await _kernel(_PROFILER_ON).boot() as booted:
        collector = await booted.container.get(SecurityDataCollector)
        async with unit_of_work(booted.container) as unit:
            manager = await unit.get(TraceableAccessDecisionManager)

    assert manager._recorder == collector.record_decision


async def test_without_the_profiler_the_traced_decision_manager_reports_to_nothing() -> None:
    async with await _kernel().boot() as booted:
        async with unit_of_work(booted.container) as unit:
            manager = await unit.get(TraceableAccessDecisionManager)

        assert not booted.container.has(SecurityDataCollector)

    assert manager._recorder is None
