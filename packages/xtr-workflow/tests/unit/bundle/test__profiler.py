"""The profiler panel is registered tagged for the profiler, and wired to every traced workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG, ProfiledRequest
from xtr_http_message import ServerRequest

from tests.fixtures.subject import Subject
from tests.support.builds import build_state, builder_of, definition_of, services_of
from xtr_workflow import Definition, Transition, Workflow
from xtr_workflow.bundle import (
    WORKFLOW_TAG,
    TransitionConfig,
    WorkflowDebugPass,
    WorkflowDefinitionConfig,
    WorkflowServiceRegistrar,
)
from xtr_workflow.bundle._profiler import (
    _profiled_traceable_workflow,
    _workflow_collector,
    register_profiler,
    wire_profiler,
)
from xtr_workflow.data_collector import WorkflowDataCollector
from xtr_workflow.debug import TraceableWorkflow
from xtr_workflow.workflow_type import WorkflowType

if TYPE_CHECKING:
    from xtr_dependency_injection.builder.service_configurator import BuildState

_PROFILED = ProfiledRequest(ServerRequest("GET", "/"), 200, {}, {})


class Article:
    pass


def _registered(state: BuildState) -> None:
    """Register the panel, an ``article`` workflow, and trace it, as a debug build does."""
    services = services_of(state)
    register_profiler(services)
    WorkflowServiceRegistrar().register(
        services,
        "article",
        WorkflowDefinitionConfig(
            type=WorkflowType.WORKFLOW,
            supports=Article,
            transitions={"go": TransitionConfig(froms="a", tos="b")},
        ),
    )
    WorkflowDebugPass().process(builder_of(state))


def test_the_collector_is_tagged_as_the_workflow_panel() -> None:
    state = build_state(debug=True)

    register_profiler(services_of(state))

    definition = definition_of(state, WorkflowDataCollector)
    assert definition.get_tag(DATA_COLLECTOR_TAG) == [
        {
            "name": "workflow",
            "template": "@xtr_workflow/collector/workflow.html.j2",
            "priority": 220,
        }
    ]
    assert definition.get_arguments() == {"workflows": ()}


def test_the_collector_is_handed_every_defined_workflow() -> None:
    state = build_state(debug=True)
    _registered(state)
    state.phase = "process"

    wire_profiler(builder_of(state))

    assert definition_of(state, WorkflowDataCollector).get_arguments() == {
        "workflows": (
            {
                "name": "article",
                "type": "workflow",
                "supports": [f"{__name__}.Article"],
            },
        )
    }


def test_every_traced_workflow_hands_its_calls_to_the_collector() -> None:
    state = build_state(debug=True)
    _registered(state)
    state.phase = "process"

    wire_profiler(builder_of(state))

    assert definition_of(state, TraceableWorkflow, "article").provider is (
        _profiled_traceable_workflow
    )


def test_a_workflow_tagged_by_hand_is_described_by_its_qualifier() -> None:
    state = build_state(debug=True)
    services = services_of(state)
    register_profiler(services)
    _ = services.set(Workflow, qualifier="by_hand").add_tag(WORKFLOW_TAG)
    WorkflowDebugPass().process(builder_of(state))
    state.phase = "process"

    wire_profiler(builder_of(state))

    assert definition_of(state, WorkflowDataCollector).get_arguments() == {
        "workflows": ({"name": "by_hand", "type": None, "supports": []},)
    }


def test_the_collector_factory_shows_the_workflows_it_is_handed() -> None:
    workflows: tuple[dict[str, object], ...] = (
        {"name": "article", "type": "workflow", "supports": []},
    )

    collector = _workflow_collector(workflows)

    assert collector.collect(_PROFILED) == {"workflows": list(workflows)}


@pytest.mark.anyio
async def test_the_profiled_traceable_workflow_records_into_the_collector_by_its_name() -> None:
    collector = WorkflowDataCollector([])
    workflow = Workflow(Definition(["a", "b"], [Transition("go", "a", "b")]), name="article")
    traceable = _profiled_traceable_workflow(workflow, collector)
    collector.begin_request()

    _ = await traceable.can(Subject({"a": 1}), "go")

    data = collector.late_collect(collector.collect(_PROFILED), _PROFILED)
    calls = cast("list[dict[str, object]]", data["calls"])
    assert traceable.get_inner() is workflow
    assert [(call["workflow"], call["method"]) for call in calls] == [("article", "can")]
