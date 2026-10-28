"""Anything that validates a definition under a workflow's name is a definition validator."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from xtr_workflow.validator import (
    DefinitionValidatorInterface,
    StateMachineValidator,
    WorkflowValidator,
)

if TYPE_CHECKING:
    from xtr_workflow import Definition


@final
class _Validator:
    """Validates a definition, deriving from nothing."""

    def validate(self, definition: Definition, name: str) -> None:
        del definition, name


@pytest.mark.parametrize(
    "validator",
    [
        pytest.param(StateMachineValidator(), id="state-machine"),
        pytest.param(WorkflowValidator(), id="workflow"),
        pytest.param(_Validator(), id="deriving-from-nothing"),
    ],
)
def test_an_object_validating_a_definition_satisfies_the_contract(validator: object) -> None:
    assert isinstance(validator, DefinitionValidatorInterface)


def test_an_object_that_cannot_validate_a_definition_does_not() -> None:
    assert not isinstance(object(), DefinitionValidatorInterface)
