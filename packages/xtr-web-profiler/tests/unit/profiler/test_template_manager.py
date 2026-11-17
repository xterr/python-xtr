from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_kernel.data_collector import DataCollectorTemplates
from xtr_http_kernel.profiler import FileProfilerStorage, Profile, Profiler

from xtr_web_profiler import TemplateManager, TemplateNotFoundError
from xtr_web_profiler.templating import create_environment

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_http_kernel.data_collector import ProfiledRequest


@final
class _Collector:
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        del profiled
        return {}


def _manager(*entries: tuple[str, str]) -> TemplateManager:
    return TemplateManager(create_environment(), DataCollectorTemplates(entries))


def _profiler(tmp_path: Path, *names: str) -> Profiler:
    return Profiler(FileProfilerStorage(tmp_path), [_Collector(name) for name in names])


def test_a_panel_is_shown_when_its_collector_is_registered_and_kept_data(tmp_path: Path) -> None:
    manager = _manager(
        ("memory", "@xtr_web_profiler/collector/memory.html.j2"),
        ("ajax", "@xtr_web_profiler/collector/ajax.html.j2"),
        ("gone", "@xtr_web_profiler/collector/ajax.html.j2"),
    )
    profile = Profile("abc", collectors={"memory": {}, "gone": {}})

    names = manager.get_names(profile, _profiler(tmp_path, "memory", "ajax"))

    assert names == [("memory", "@xtr_web_profiler/collector/memory.html.j2")]


def test_a_collector_naming_a_missing_template_is_refused(tmp_path: Path) -> None:
    manager = _manager(("orm", "@xtr_web_profiler/collector/orm.html.j2"))

    with pytest.raises(TemplateNotFoundError, match='"orm"') as caught:
        _ = manager.get_names(Profile("abc", collectors={"orm": {}}), _profiler(tmp_path, "orm"))

    assert caught.value.template == "@xtr_web_profiler/collector/orm.html.j2"


def test_a_block_the_template_lacks_renders_empty() -> None:
    manager = _manager()

    html = manager.render_block("@xtr_web_profiler/profiler/toolbar_item.html.j2", "panel", {})

    assert html == ""
