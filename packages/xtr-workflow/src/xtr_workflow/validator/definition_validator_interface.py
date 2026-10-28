"""Checking a definition before a workflow runs it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_workflow.definition import Definition

__all__ = ["DefinitionValidatorInterface"]


@runtime_checkable
class DefinitionValidatorInterface(Protocol):
    """Checks that a definition can run as the workflow it is meant for.

    A definition takes any places and any transitions; whether they can run
    depends on what runs them — a state machine moves its subject from one
    place to one place, a marking store keeping one place per subject has
    nowhere to put a second. A validator holds a definition to those rules
    before a workflow runs it, so a mistake shows where the definition is
    made rather than halfway through a move.

    Checking reads nothing but the definition, so it is not a coroutine: a
    definition is checked wherever it is built, the container's build
    included.
    """

    def validate(self, definition: Definition, name: str) -> None:
        """Refuse ``definition`` unless the workflow ``name`` can run it.

        Args:
            definition: The definition to check.
            name: The name of the workflow it defines, quoted in the error.

        Raises:
            InvalidDefinitionError: If the definition breaks one of the
                validator's rules.
        """
        ...
