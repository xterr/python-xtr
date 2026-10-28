"""Anything that tells whether a workflow supports a subject is a support strategy."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from xtr_workflow.support_strategy import (
    InstanceOfSupportStrategy,
    WorkflowSupportStrategyInterface,
)

if TYPE_CHECKING:
    from xtr_workflow import WorkflowInterface


@final
class _Strategy:
    """Supports every subject, deriving from nothing."""

    def supports(self, workflow: WorkflowInterface, subject: object) -> bool:
        del workflow, subject
        return True


@pytest.mark.parametrize(
    "strategy",
    [
        pytest.param(InstanceOfSupportStrategy(object), id="instance-of"),
        pytest.param(_Strategy(), id="deriving-from-nothing"),
    ],
)
def test_an_object_telling_whether_a_workflow_supports_a_subject_satisfies_the_contract(
    strategy: object,
) -> None:
    assert isinstance(strategy, WorkflowSupportStrategyInterface)


def test_an_object_that_cannot_tell_does_not() -> None:
    assert not isinstance(object(), WorkflowSupportStrategyInterface)
