"""The services the configuration names, what a listener writes to, and who injects workflows."""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Injected, ServiceLocator, Target, as_service
from xtr_event_dispatcher.decorator import as_event_listener

from tests.fixtures.app_workflow.subjects import Ticket
from xtr_workflow import WorkflowInterface
from xtr_workflow.event import GuardEvent
from xtr_workflow.marking_store import MarkingStoreInterface, MethodMarkingStore
from xtr_workflow.support_strategy import WorkflowSupportStrategyInterface


@as_service(qualifier="workflow_service")
def workflow_service() -> MarkingStoreInterface:
    return MethodMarkingStore(marking_property="marking")


@final
class TicketSupport(WorkflowSupportStrategyInterface):
    @override
    def supports(self, workflow: WorkflowInterface, subject: object) -> bool:
        return isinstance(subject, Ticket)


@as_service(qualifier="ticket_support")
def ticket_support() -> WorkflowSupportStrategyInterface:
    return TicketSupport()


@final
@as_service
class Journal:
    def __init__(self) -> None:
        self.guarded: list[str] = []


@as_event_listener()
def on_guard(event: GuardEvent, journal: Injected[Journal]) -> None:
    """Declares the event by its class, which the workflow dispatches by name."""
    journal.guarded.append(f"{event.get_workflow_name()}.{event.get_transition().get_name()}")


@final
@as_service
class WorkflowConsumer:
    def __init__(
        self,
        article: Annotated[WorkflowInterface, Target("article")],
        workflows: ServiceLocator[WorkflowInterface],
    ) -> None:
        self.article = article
        self.workflows = workflows
