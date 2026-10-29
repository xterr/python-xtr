"""Every request a rate limit turned away, written to the ``security`` channel.

A limiter only answers; whoever refuses the hit announces it. For the web routes that is the
http kernel's ``RateLimited``, which dispatches a ``RateLimitExceededEvent`` naming the limiter
and the key before answering 429 — so the audit needs no code in any route.
"""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher import as_event_listener
from xtr_logging_contracts import LoggerInterface
from xtr_rate_limiter import RateLimitExceededEvent

__all__ = ["audit_refused_request"]


@as_event_listener()
async def audit_refused_request(
    event: RateLimitExceededEvent, logger: Annotated[LoggerInterface, Target("security")]
) -> None:
    """Write who was refused, by which limit, and when they may come back."""
    logger.warning(
        "rate limit {limiter} refused {key} until {retry_after}",
        {
            "limiter": event.limiter_name,
            "key": event.key,
            "retry_after": event.rate_limit.retry_after.isoformat(),
        },
    )
