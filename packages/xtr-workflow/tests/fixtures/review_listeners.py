"""Listeners of a review, written once on a base class that several workflow classes share.

None of them names a workflow: each workflow class deriving this one makes
them listen to its own.
"""

from __future__ import annotations

from xtr_workflow.decorator import (
    as_announce_listener,
    as_completed_listener,
    as_enter_listener,
    as_entered_listener,
    as_guard_listener,
    as_leave_listener,
)
from xtr_workflow.event import (
    AnnounceEvent,
    CompletedEvent,
    EnteredEvent,
    EnterEvent,
    GuardEvent,
    LeaveEvent,
)


class ReviewListeners:
    def __init__(self) -> None:
        self.heard: list[str] = []

    @as_guard_listener(transition="approve", priority=5)
    def guard_approve(self, event: GuardEvent) -> None:
        self.heard.append(f"guard {event.get_workflow_name()}")

    @as_completed_listener()
    @as_entered_listener(place="approved")
    def on_review(self, event: CompletedEvent | EnteredEvent) -> None:
        self.heard.append(f"review {event.get_workflow_name()}")

    @as_enter_listener(place="approved")
    async def enter_approved(self, event: EnterEvent) -> None:
        self.heard.append(f"enter {event.get_workflow_name()}")

    @staticmethod
    @as_announce_listener(transition="approve")
    def announce(event: AnnounceEvent) -> str:
        return f"announce {event.get_workflow_name()}"

    @as_leave_listener(place="draft")
    @classmethod
    def leave_draft(cls, event: LeaveEvent) -> str:
        return f"{cls.__name__} leaves {event.get_workflow_name()}"

    @as_guard_listener("other", "approve")
    def guard_other(self, _event: GuardEvent) -> None: ...

    def describe(self) -> str:
        return type(self).__name__
