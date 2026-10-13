"""What decides whether a failed request is worth making again.

:class:`RetryStrategyInterface` is the decision, asked about one attempt at a
time — a :class:`RetryContext` — and :class:`GenericRetryStrategy` is the
answer most applications want: the status codes worth retrying, for the
methods worth retrying them for, with a delay that grows between attempts.
"""

from __future__ import annotations

from .generic_retry_strategy import (
    DEFAULT_RETRY_STATUS_CODES,
    IDEMPOTENT_METHODS,
    GenericRetryStrategy,
)
from .retry_context import RetryContext
from .retry_strategy_interface import RetryStrategyInterface

__all__ = [
    "DEFAULT_RETRY_STATUS_CODES",
    "IDEMPOTENT_METHODS",
    "GenericRetryStrategy",
    "RetryContext",
    "RetryStrategyInterface",
]
