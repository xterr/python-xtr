"""Anything that moves subjects and reads its accessors the way a workflow does is a workflow."""

from __future__ import annotations

from typing import final

from tests.support.workflow_stub import WorkflowStub
from xtr_workflow import WorkflowInterface


@final
class _NameOnly:
    def get_name(self) -> str:
        return "article"


def test_an_object_with_every_method_of_a_workflow_satisfies_the_contract() -> None:
    assert isinstance(WorkflowStub(), WorkflowInterface)


def test_an_object_that_only_has_a_name_does_not() -> None:
    assert not isinstance(_NameOnly(), WorkflowInterface)
