"""Shows redirects as pages of their own, and reloads the toolbar after background requests."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_web_profiler.bundle import WebProfilerConfig


@configure
def web_profiler() -> WebProfilerConfig:
    return WebProfilerConfig(
        intercept_redirects=True, ajax_replace=True, file_link_format="vscode://file/{file}:{line}"
    )
