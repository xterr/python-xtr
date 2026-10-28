"""A kernel registers every workflow its scan finds declared on a class, with its listeners."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test

from tests.fixtures.app_workflow_declared.workflows import Chore, ChoreStateMachine, TaskConsumer
from tests.fixtures.task import Task
from tests.fixtures.task_step import TaskStep
from xtr_workflow import Registry, StateMachine, WorkflowInterface
from xtr_workflow.debug import TraceableWorkflow

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    from xtr_dependency_injection import BootedKernel

pytestmark = pytest.mark.anyio


async def booted(*, debug: bool = False) -> AbstractAsyncContextManager[BootedKernel]:
    kernel = Kernel("tests.fixtures.app_workflow_declared", env="test", debug=debug)
    return await boot_for_test(kernel)


async def test_the_workflow_of_a_class_is_registered_and_handed_to_it() -> None:
    async with await booted() as kernel:
        consumer = await kernel.container.get(TaskConsumer)
        registry = await kernel.container.get(Registry)
        task = Task()

        can_start = await consumer.task_workflow.can(task, consumer.task_workflow.START)
        _ = await consumer.task_workflow.start(task)
        can_finish = await consumer.task_workflow.can(task, consumer.task_workflow.FINISH)
        can_fail = await consumer.task_workflow.can(task, consumer.task_workflow.FAIL)
        blocked_task = Task()
        blocked_task.blocked = True
        can_start_blocked = await consumer.task_workflow.can(
            blocked_task, consumer.task_workflow.START
        )

    workflow = consumer.workflow
    definition = consumer.task_workflow.get_definition()
    assert type(workflow) is StateMachine
    assert consumer.task_workflow.get_name() == "task"
    assert definition is workflow.get_definition()
    assert list(definition.get_places()) == ["new", "processing", "done", "failed"]
    assert definition.get_initial_places() == ["new"]
    assert consumer.task_workflow.get_metadata_store().get_metadata("title") == "Task"
    assert (
        consumer.task_workflow.get_metadata_store().get_metadata("label", TaskStep.PROCESSING)
        == "Processing"
    )
    assert can_start
    assert task.step is TaskStep.PROCESSING
    assert task.context == {"started_by": "start()"}, "the transition listener of the class runs"
    assert can_finish
    assert can_fail
    assert not can_start_blocked, "the guard listener of the class runs"
    assert registry.all(task) == [workflow]


async def test_a_listener_of_a_workflow_class_hears_only_its_own_workflow() -> None:
    async with await booted() as kernel:
        chores = await kernel.container.get(WorkflowInterface, "chore")
        chore = Chore()

        can_start = await chores.can(chore, ChoreStateMachine.START)

    assert can_start, "the task workflow's guard of its start transition does not run"


async def test_in_debug_mode_the_class_answers_for_the_traced_workflow() -> None:
    async with await booted(debug=True) as kernel:
        consumer = await kernel.container.get(TaskConsumer)

        _ = await consumer.task_workflow.start(Task())

    assert isinstance(consumer.workflow, TraceableWorkflow)
    assert [call["method"] for call in consumer.workflow.get_calls()] == ["apply"]
