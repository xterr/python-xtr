"""The application's own retry strategy, which a scoped client names."""

from __future__ import annotations

from xtr_dependency_injection import as_service

from xtr_http_client import GenericRetryStrategy, RetryStrategyInterface

TEAPOT = "teapot"


@as_service(qualifier=TEAPOT)
def teapot_strategy() -> RetryStrategyInterface:
    # A code the default strategy never retries, so a retry proves this one decided.
    return GenericRetryStrategy([418], delay_ms=0)
