from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import ContainerBuilder, Kernel, bundle_active
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.data_collector import DataCollectorTemplates

from xtr_mailer.bundle import MailerBundle
from xtr_mailer.bundle import _profiler as profiler_module
from xtr_mailer.data_collector import MailerDataCollector

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))


def _kernel() -> Kernel:
    return Kernel(
        __name__,
        env="test",
        bundles={MailerBundle: {"all": True}, HttpKernelBundle: {"all": True}},
        resources=("tests.fixtures.profiler_on",),
    )


async def test_the_collector_is_tagged_with_its_panel_template() -> None:
    async with await _kernel().boot() as booted:
        templates = await booted.container.get(DataCollectorTemplates)

    assert templates.template_of("mailer") == "@xtr_mailer/collector/mailer.html.j2"


async def test_without_the_event_dispatcher_no_collector_is_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def active(builder: ContainerBuilder, name: str) -> bool:
        return name != "event_dispatcher" and bundle_active(builder, name)

    monkeypatch.setattr(profiler_module, "bundle_active", active)

    async with await _kernel().boot() as booted:
        assert not booted.container.has(MailerDataCollector)
