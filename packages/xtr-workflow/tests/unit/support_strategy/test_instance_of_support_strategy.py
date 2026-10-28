"""An instance-of strategy supports the subjects that are instances of its class."""

from __future__ import annotations

from typing import final

from tests.support.workflow_stub import WorkflowStub
from xtr_workflow.support_strategy import InstanceOfSupportStrategy


class Subject1:
    """A subject class another derives from."""


@final
class Subject2:
    """A subject class unrelated to the first."""


@final
class Subject1Subclass(Subject1):
    """A subject class deriving from the first."""


def test_it_supports_an_instance_of_its_class() -> None:
    strategy = InstanceOfSupportStrategy(Subject1)

    assert strategy.supports(WorkflowStub(), Subject1())


def test_it_does_not_support_an_instance_of_another_class() -> None:
    strategy = InstanceOfSupportStrategy(Subject2)

    assert not strategy.supports(WorkflowStub(), Subject1())


def test_it_supports_an_instance_of_a_class_deriving_from_its_class() -> None:
    strategy = InstanceOfSupportStrategy(Subject1)

    assert strategy.supports(WorkflowStub(), Subject1Subclass())


def test_it_returns_the_class_whose_instances_it_supports() -> None:
    strategy = InstanceOfSupportStrategy(Subject1)

    assert strategy.get_class_name() is Subject1
