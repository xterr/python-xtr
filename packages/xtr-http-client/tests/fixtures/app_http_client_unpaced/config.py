"""A default client paced by a rate limiter, in an application with no rate limiter bundle."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_http_client.bundle import ClientOptionsConfig, HttpClientConfig


@configure
def http_client() -> HttpClientConfig:
    return HttpClientConfig(default_options=ClientOptionsConfig(rate_limiter="api"))
