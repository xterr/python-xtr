"""Configured and declared workflows live side by side, each name taken once."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test

from xtr_workflow import Registry
from xtr_workflow.exception import LogicError

pytestmark = pytest.mark.anyio


async def test_configured_and_declared_workflows_coexist() -> None:
    kernel = Kernel("tests.fixtures.app_workflow_both", env="test", debug=False)
    async with await boot_for_test(kernel) as booted:
        registry = await booted.container.get(Registry)

    assert [workflow.get_name() for workflow in registry.all(object())] == ["article", "task"]


def test_a_class_cannot_declare_a_workflow_the_configuration_defines() -> None:
    kernel = Kernel("tests.fixtures.app_workflow_duplicate", env="test", debug=False)

    with pytest.raises(LogicError) as raised:
        _ = kernel.build()

    assert str(raised.value) == (
        'The workflow "task" defined by "tests.fixtures.app_workflow_duplicate.workflows.'
        'TaskWorkflow" is already defined by the configuration.'
    )


def test_two_classes_cannot_declare_the_same_workflow() -> None:
    kernel = Kernel("tests.fixtures.app_workflow_twice", env="test", debug=False)

    with pytest.raises(LogicError) as raised:
        _ = kernel.build()

    module = "tests.fixtures.app_workflow_twice.workflows"
    assert str(raised.value) == (
        f'The workflow "task" defined by "{module}.OtherTaskWorkflow" is already defined by '
        f'"{module}.TaskWorkflow".'
    )


def test_a_function_listening_to_a_transition_of_no_workflow_fails_the_build() -> None:
    kernel = Kernel("tests.fixtures.app_workflow_misplaced", env="test", debug=False)

    with pytest.raises(LogicError) as raised:
        _ = kernel.build()

    assert str(raised.value) == (
        'The "tests.fixtures.app_workflow_misplaced.listeners.guard()" listener listens to a '
        'transition or a place without defining the "workflow" argument of its decorator; set '
        'it, or move the listener to a class using the "@as_workflow" decorator.'
    )
