"""A function listener naming a transition, which only a workflow class can make its own."""

from __future__ import annotations

from xtr_workflow.decorator import as_guard_listener
from xtr_workflow.event import GuardEvent


@as_guard_listener(transition="go")
def guard(_event: GuardEvent) -> None: ...
