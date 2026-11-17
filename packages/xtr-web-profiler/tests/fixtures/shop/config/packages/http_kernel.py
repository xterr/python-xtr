"""Keeps the profiles where the test reads them; the web profiler turns profiling on."""

from __future__ import annotations

import os

from xtr_dependency_injection import configure
from xtr_http_kernel.bundle import HttpKernelConfig, ProfilerConfig


@configure
def http_kernel() -> HttpKernelConfig:
    return HttpKernelConfig(
        profiler=ProfilerConfig(storage_path=os.environ.get("PROFILER_TEST_FOLDER"))
    )
