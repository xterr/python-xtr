"""The workflow bundle builds and boots unconfigured, and traces workflows in debug mode only."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config

from tests.support.builds import build_state, builder_of
from xtr_workflow import Registry
from xtr_workflow.bundle import WorkflowBundle, WorkflowDebugPass
from xtr_workflow.exception import InvalidArgumentError


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
