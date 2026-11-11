"""What run control knows about one run."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, final

from xtr_ai.run_state import RunState

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from pydantic_ai.usage import RunUsage

__all__ = ["RunStatus"]


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class RunStatus:
    """A run as run control recorded it.

    Attributes:
        run_id: The run.
        agent: The agent that runs it.
        state: Where it stands.
        conversation_id: The conversation it belongs to, if any.
        parent_run_id: The run that started it, for a run delegated from another.
        cancel_requested: Whether cancellation was asked for.
        usage: Its usage, once it ended and the usage was recorded.
        metadata: What the application stored with it — an owner to check, a request id.
        started_at: When it started.
        heartbeat_at: When its process last reported it alive.
        finished_at: When it ended, if it did.
    """

    run_id: str
    agent: str
    state: RunState
    conversation_id: str | None = None
    parent_run_id: str | None = None
    cancel_requested: bool = False
    usage: RunUsage | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    started_at: datetime
    heartbeat_at: datetime
    finished_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        """Whether the run is still in progress."""
        return self.state is RunState.RUNNING

    @property
    def holds_conversation(self) -> bool:
        """Whether the run keeps another top-level run of its conversation from starting."""
        return self.is_running and self.conversation_id is not None and self.parent_run_id is None
