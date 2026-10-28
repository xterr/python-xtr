"""Finding the workflow that moves a subject."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .support_strategy import WorkflowSupportStrategyInterface
    from .workflow_interface import WorkflowInterface

__all__ = ["Registry"]


@final
class Registry:
    """Finds the workflows that move a subject, among those added to it.

    Each workflow is added with a support strategy telling which subjects it
    moves. One subject can move through several workflows — a post can be
    published and moderated — so asking by subject alone finds one only while
    no other supports the subject too; asking by name as well tells them
    apart.

    Errors name a subject's class by its bare name, as every error of this
    package names a class: ``object`` for a plain ``object()``.

    Nothing it does asks a listener, so nothing in it is a coroutine.
    """

    __slots__: tuple[str, ...] = ("_workflows",)

    _workflows: list[tuple[WorkflowInterface, WorkflowSupportStrategyInterface]]

    def __init__(self) -> None:
        """Hold no workflow until one is added."""
        self._workflows = []

    def add_workflow(
        self, workflow: WorkflowInterface, support_strategy: WorkflowSupportStrategyInterface
    ) -> None:
        """Add ``workflow``, for the subjects ``support_strategy`` supports."""
        self._workflows.append((workflow, support_strategy))

    def has(self, subject: object, workflow_name: str | None = None) -> bool:
        """Tell whether a workflow supports ``subject``.

        Args:
            subject: The object to move.
            workflow_name: The name the workflow must have; any when ``None``.
        """
        return next(self._supporting(subject, workflow_name), None) is not None

    def get(self, subject: object, workflow_name: str | None = None) -> WorkflowInterface:
        """Return the one workflow supporting ``subject``.

        Args:
            subject: The object to move.
            workflow_name: The name the workflow must have; any when ``None``.

        Raises:
            InvalidArgumentError: If no workflow supports ``subject``, or
                several do and ``workflow_name`` does not pick one out.
        """
        matched = list(self._supporting(subject, workflow_name))
        if not matched:
            raise InvalidArgumentError(
                f'Unable to find a workflow for class "{type(subject).__name__}".'
            )
        if len(matched) > 1:
            names = ", ".join(workflow.get_name() for workflow in matched)
            raise InvalidArgumentError(
                f"Too many workflows ({names}) match this subject ({type(subject).__name__}); "
                "set a different name on each and use the second (name) argument of this method."
            )
        return matched[0]

    def all(self, subject: object) -> list[WorkflowInterface]:
        """Return every workflow supporting ``subject``, in the order they were added."""
        return list(self._supporting(subject, None))

    def _supporting(
        self, subject: object, workflow_name: str | None
    ) -> Iterator[WorkflowInterface]:
        """Yield the workflows supporting ``subject``, in the order they were added.

        Only a workflow named ``workflow_name``, when it is given, has its
        strategy asked.
        """
        for workflow, support_strategy in self._workflows:
            if workflow_name is not None and workflow.get_name() != workflow_name:
                continue
            if support_strategy.supports(workflow, subject):
                yield workflow
