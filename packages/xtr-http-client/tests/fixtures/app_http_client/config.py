"""A default client answering from a script, and a scoped client per layer around one."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_rate_limiter import LimiterConfig
from xtr_rate_limiter.bundle import RateLimiterConfig

from xtr_http_client.bundle import (
    ClientOptionsConfig,
    HttpClientConfig,
    RetryFailedConfig,
    ScopedClientConfig,
)

from .services import TEAPOT


@configure
def rate_limiter() -> RateLimiterConfig:
    return RateLimiterConfig(
        limiters={
            "api": LimiterConfig(
                "fixed_window", limit=5, interval="1 minute", storage="in-memory", lock=None
            ),
        },
    )


@configure
def http_client() -> HttpClientConfig:
    return HttpClientConfig(
        mock_response_factory=True,
        tracing=True,
        default_options=ClientOptionsConfig(
            retry_failed=RetryFailedConfig(enabled=True, max_retries=1, delay=0),
        ),
        scoped_clients={
            "github": ScopedClientConfig(
                base_uri="https://api.github.test/",
                headers={"Accept": "application/vnd.github+json"},
            ),
            "paced": ScopedClientConfig(scope=r"https://paced\.test/", rate_limiter="api"),
            "fallback": ScopedClientConfig(
                base_uri="https://primary.test/",
                retry_failed=RetryFailedConfig(
                    enabled=True, delay=0, base_uris=("https://secondary.test/",)
                ),
            ),
            "teapot": ScopedClientConfig(
                base_uri="https://teapot.test/",
                retry_failed=RetryFailedConfig(enabled=True, retry_strategy=TEAPOT),
            ),
            "real": ScopedClientConfig(base_uri="https://real.test/", mock_response_factory=False),
        },
    )
