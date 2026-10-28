"""The workflow bundle builds and boots unconfigured, and traces workflows in debug mode only.

Listed alone, it brings the event dispatcher, logging and console bundles of
the packages installed beside it, and never the security bundle: guards need
an application to list that one.

With a console, it adds the dump command, built with the workflows and, when
the event dispatcher is active, the dispatcher their listeners are on.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel, ServiceLocator
from xtr_dependency_injection.testing import assert_zero_config
from xtr_event_dispatcher_contracts import ListenerIntrospectionInterface

from tests.support.builds import build_state, builder_of, definition_of, services_of
from xtr_workflow import Registry, WorkflowInterface
from xtr_workflow.bundle import WorkflowBundle, WorkflowConfig, WorkflowDebugPass
from xtr_workflow.command import WorkflowDumpCommand
from xtr_workflow.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.anyio
async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(WorkflowBundle)


@pytest.mark.anyio
async def test_with_no_configuration_the_registry_finds_no_workflow() -> None:
    kernel = Kernel(
        WorkflowBundle.__module__,
        env="test",
        bundles={WorkflowBundle: {"all": True}},
        resources=(),
    )
    async with await kernel.boot() as booted:
        registry = await booted.container.get(Registry)

    with pytest.raises(InvalidArgumentError) as raised:
        _ = registry.get(object())

    assert str(raised.value) == 'Unable to find a workflow for class "object".'


def _activated_by_listing_the_workflow_bundle_alone() -> dict[str, str]:
    """Return each bundle the build activates, mapped to why: kernel, listed or required."""
    # No resources: the bundle and the peers it pulls in are the whole build.
    compiled = Kernel(
        WorkflowBundle.__module__,
        env="test",
        bundles={WorkflowBundle: {"all": True}},
        resources=(),
    ).build()
    return {
        report.name: report.source for report in compiled.report.bundles if report.state == "active"
    }


def test_the_security_bundle_is_not_activated_unless_the_application_lists_it() -> None:
    # xtr-security is installed here, as it is beside an application whose workflows have guards.
    activated = _activated_by_listing_the_workflow_bundle_alone()

    assert "security" not in activated


@pytest.mark.parametrize("peer", ["event_dispatcher", "logging", "console"])
def test_a_peer_whose_package_is_installed_comes_along_unlisted(peer: str) -> None:
    activated = _activated_by_listing_the_workflow_bundle_alone()

    assert activated[peer] == "required"


@pytest.mark.parametrize("debug", [False, True])
def test_the_debug_pass_is_added_in_debug_mode_only(debug: bool) -> None:
    state = build_state(debug=debug)
    state.phase = "build"

    WorkflowBundle().build(builder_of(state))

    passes = state.compiler.get_pass_config().get_before_optimization_passes()
    assert any(isinstance(compiler_pass, WorkflowDebugPass) for compiler_pass in passes) is debug


def test_the_build_reads_workflows_and_misplaced_listeners_off_the_scan() -> None:
    state = build_state()
    state.phase = "build"

    WorkflowBundle().build(builder_of(state))

    assert [autoconfigurator.owner for autoconfigurator in state.autoconfigurators] == [
        "workflow",
        "workflow",
    ]


@pytest.mark.parametrize(
    ("bundles", "late_scans"),
    [((), []), (("console",), [("workflow", ("xtr_workflow.command",))])],
)
def test_the_dump_command_is_loaded_with_a_console_only(
    bundles: tuple[str, ...], late_scans: list[tuple[str, tuple[str, ...]]]
) -> None:
    state = build_state(bundles=bundles)

    WorkflowBundle().load_extension(WorkflowConfig(), services_of(state), builder_of(state))

    assert state.late_scans == late_scans


@pytest.mark.parametrize(
    ("bundles", "injected"),
    [
        (("console",), {"workflows": ServiceLocator[WorkflowInterface]}),
        (
            ("console", "event_dispatcher"),
            {
                "workflows": ServiceLocator[WorkflowInterface],
                "dispatcher": ListenerIntrospectionInterface,
            },
        ),
    ],
)
def test_the_dump_command_is_built_with_the_workflows_and_any_active_dispatcher(
    bundles: tuple[str, ...], injected: dict[str, object]
) -> None:
    state = build_state(bundles=bundles)
    # As the console registers a command class its scan finds.
    _ = services_of(state).set(WorkflowDumpCommand)
    state.phase = "process"

    WorkflowBundle().process(builder_of(state))

    definition = definition_of(state, WorkflowDumpCommand)
    factory = cast("Callable[..., object]", definition.provider)
    parameters = inspect.signature(factory).parameters.values()
    assert definition.kind == "factory"
    assert {
        parameter.name: cast("object", parameter.annotation) for parameter in parameters
    } == injected


def test_without_a_console_there_is_no_command_to_build() -> None:
    state = build_state(bundles=("event_dispatcher",))
    state.phase = "process"

    WorkflowBundle().process(builder_of(state))

    assert state.store.entries() == ()
