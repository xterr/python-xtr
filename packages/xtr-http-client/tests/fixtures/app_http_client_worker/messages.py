"""The message the fixture application queues."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Ping:
    """Queued for a worker, whose handler takes the default HTTP client."""

    number: int
