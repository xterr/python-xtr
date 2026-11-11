"""Where run control keeps its runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TypeAlias, final

from xtr_ai.abstract_run_control import (
    DEFAULT_CANCEL_POLL_INTERVAL,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_STALE_AFTER,
)
from xtr_ai.run_control_interface import RunControlInterface

__all__ = [
    "InMemoryRunControlConfig",
    "OrmRunControlConfig",
    "RunControlEntry",
    "ServiceRunControlConfig",
]


@final
@dataclass(frozen=True, slots=True)
class InMemoryRunControlConfig:
    """Runs held in memory: one process only.

    Attributes:
        cancel_poll_interval: Seconds between two reads of a watched run's cancel flag.
        heartbeat_interval: How often a watched run reports itself alive.
        stale_after: How long a silent run keeps its conversation.
    """

    cancel_poll_interval: float = DEFAULT_CANCEL_POLL_INTERVAL
    heartbeat_interval: timedelta = DEFAULT_HEARTBEAT_INTERVAL
    stale_after: timedelta = DEFAULT_STALE_AFTER


@final
@dataclass(frozen=True, slots=True)
class OrmRunControlConfig:
    """Runs in a table on an xtr-orm connection, shared by every process using it.

    Needs ``xtr-ai-orm-run-control`` and OrmBundle.

    Attributes:
        connection: The orm connection whose primary keeps the table.
        table_prefix: What the table name starts with.
        cancel_poll_interval: Seconds between two reads of a watched run's cancel flag.
        heartbeat_interval: How often a watched run reports itself alive.
        stale_after: How long a silent run keeps its conversation.
    """

    connection: str = "default"
    table_prefix: str = "ai_"
    cancel_poll_interval: float = DEFAULT_CANCEL_POLL_INTERVAL
    heartbeat_interval: timedelta = DEFAULT_HEARTBEAT_INTERVAL
    stale_after: timedelta = DEFAULT_STALE_AFTER


@final
@dataclass(frozen=True, slots=True)
class ServiceRunControlConfig:
    """A run control the application registers itself, under its class."""

    service: type[RunControlInterface]


RunControlEntry: TypeAlias = (
    InMemoryRunControlConfig | OrmRunControlConfig | ServiceRunControlConfig
)
"""What ``AiConfig.runs`` holds."""
