"""Recording, in debug mode, every call made to every workflow."""

from __future__ import annotations

from typing import Annotated, Final, final

from xtr_dependency_injection import AutowireDecorated, ContainerBuilder, Definition, Origin

from xtr_workflow.debug import TraceableWorkflow
from xtr_workflow.workflow_interface import WorkflowInterface

from .workflow_service_registrar import WORKFLOW_TAG

__all__ = ["WorkflowDebugPass"]

_ORIGIN: Final = Origin("bundle", "workflow")


@final
class WorkflowDebugPass:
    """Wraps every service tagged ``workflow`` in a :class:`TraceableWorkflow`.

    The workflows the bundle registers, and any the application registers
    and tags itself: whatever asks for one — by its name, through a locator,
    through the registry — gets the traced one, and the record of its calls
    is cleared between units of work.

    The bundle adds the pass in debug mode only.
    """

    __slots__ = ()

    def process(self, builder: ContainerBuilder) -> None:
        """Decorate each workflow with a traceable one, reset between units of work."""
        for service, qualifier in builder.find_tagged_service_ids(WORKFLOW_TAG):
            _ = builder.set_definition(
                Definition(
                    (TraceableWorkflow, qualifier),
                    _traceable_workflow,
                    "factory",
                    "singleton",
                    _ORIGIN,
                )
                .set_decorated_service(service, qualifier=qualifier)
                .add_tag("kernel.reset", method="reset")
            )


def _traceable_workflow(
    workflow: Annotated[WorkflowInterface, AutowireDecorated()],
) -> TraceableWorkflow:
    """Trace ``workflow``, timed against a monotonic clock."""
    return TraceableWorkflow(workflow)
