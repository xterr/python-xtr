"""Turns profiling off again, the web profiler listed all the same."""

from __future__ import annotations

from dataclasses import replace

from xtr_dependency_injection import configure
from xtr_http_kernel.bundle import HttpKernelConfig  # noqa: TC002 — read at runtime by the kernel


@configure
def http_kernel(config: HttpKernelConfig) -> HttpKernelConfig:
    return replace(config, profiler=replace(config.profiler, enabled=False))
