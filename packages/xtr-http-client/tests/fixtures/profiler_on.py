"""Profiles every request, with clients answering from a script."""

from __future__ import annotations

import os

from xtr_dependency_injection import configure
from xtr_http_kernel.bundle import HttpKernelConfig, ProfilerConfig

from xtr_http_client.bundle import HttpClientConfig, ScopedClientConfig


@configure
def http_kernel() -> HttpKernelConfig:
    return HttpKernelConfig(
        profiler=ProfilerConfig(enabled=True, storage_path=os.environ.get("PROFILER_TEST_FOLDER"))
    )


@configure
def http_client() -> HttpClientConfig:
    return HttpClientConfig(
        mock_response_factory=True,
        scoped_clients={"github": ScopedClientConfig(base_uri="https://api.github.test/")},
    )
