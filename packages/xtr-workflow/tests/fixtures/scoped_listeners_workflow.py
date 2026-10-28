"""A workflow class whose listeners name its workflow, another one, or none at all."""

from __future__ import annotations

from typing import Annotated, ClassVar, final

from xtr_event_dispatcher.decorator import as_event_listener

from xtr_workflow.decorator import Transition, as_completed_listener, as_guard_listener, as_workflow
from xtr_workflow.event import GuardEvent


@final
@as_workflow(supports=object)
@as_completed_listener(method="on_completed")
class ScopedListenersWorkflow:
    GO: ClassVar[Annotated[str, Transition(froms="a", tos="b")]] = "go"

    @as_guard_listener()
    def guard_all(self, _event: GuardEvent) -> None: ...

    @as_guard_listener(transition=GO)
    def guard_go(self, _event: GuardEvent) -> None: ...

    @as_guard_listener("other")
    def guard_other(self, _event: GuardEvent) -> None: ...

    @as_event_listener("workflow.guard")
    def guard_every_workflow(self, _event: GuardEvent) -> None: ...

    def on_completed(self) -> None: ...
