"""The workflows' profiler panel, registered while the http kernel profiles requests in debug mode.

Imported only once the http kernel's bundle is active with its profiler on,
which proves xtr-http-kernel installed. The panel reads the calls the traced
workflows make, and they are traced in debug mode only. Every factory here is
read by the container, so the types its parameters name are imported at
runtime.
"""

from __future__ import annotations

from functools import partial
from typing import Annotated, Final, cast

from xtr_dependency_injection import AutowireDecorated, ContainerBuilder, ServiceConfigurator
from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG

from xtr_workflow.data_collector import WorkflowDataCollector
from xtr_workflow.debug import TraceableWorkflow
from xtr_workflow.decorator._workflow_name import class_name
from xtr_workflow.workflow_interface import WorkflowInterface
from xtr_workflow.workflow_type import WorkflowType

from .workflow_service_registrar import WORKFLOW_TAG

__all__ = ["register_profiler", "wire_profiler"]

_NAME: Final = "workflow"
_TEMPLATE: Final = "@xtr_workflow/collector/workflow.html.j2"
_PRIORITY: Final = 220


def register_profiler(services: ServiceConfigurator) -> None:
    """Register the panel's collector, handed the defined workflows by :func:`wire_profiler`."""
    _ = (
        services.set(_workflow_collector)
        .set_argument("workflows", ())
        .add_tag(DATA_COLLECTOR_TAG, name=_NAME, template=_TEMPLATE, priority=_PRIORITY)
    )


def wire_profiler(builder: ContainerBuilder) -> None:
    """Hand the collector every defined workflow, and every traced workflow the collector.

    Run once every workflow is registered and wrapped — the declared ones
    included, which the scan adds after the bundle's own are loaded.
    """
    workflows: list[dict[str, object]] = []
    for (_service, qualifier), tags in builder.find_tagged_service_ids(WORKFLOW_TAG).items():
        workflows.extend(_defined(attributes, qualifier) for attributes in tags)
        builder.get_definition(
            TraceableWorkflow, qualifier=qualifier
        ).provider = _profiled_traceable_workflow
    _ = builder.get_definition(WorkflowDataCollector).set_argument("workflows", tuple(workflows))


def _defined(attributes: dict[str, object], qualifier: object) -> dict[str, object]:
    """Describe a workflow by its tag: a service tagged by hand may say nothing but its name."""
    workflow_type = attributes.get("type")
    supports = attributes.get("supports")
    supported = cast("tuple[object, ...]", supports) if isinstance(supports, tuple) else ()
    return {
        "name": str(attributes.get("name", qualifier)),
        "type": workflow_type.value if isinstance(workflow_type, WorkflowType) else None,
        "supports": [class_name(item) for item in supported if isinstance(item, type)],
    }


def _workflow_collector(workflows: tuple[dict[str, object], ...]) -> WorkflowDataCollector:
    return WorkflowDataCollector(workflows)


def _profiled_traceable_workflow(
    workflow: Annotated[WorkflowInterface, AutowireDecorated()],
    collector: WorkflowDataCollector,
) -> TraceableWorkflow:
    """Trace ``workflow``, handing each call to the panel of the request being profiled too."""
    return TraceableWorkflow(workflow, recorder=partial(collector.record, workflow.get_name()))
