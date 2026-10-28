"""Supporting the subjects that are instances of a class."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .workflow_support_strategy_interface import WorkflowSupportStrategyInterface

if TYPE_CHECKING:
    from xtr_workflow.workflow_interface import WorkflowInterface

__all__ = ["InstanceOfSupportStrategy"]


@final
class InstanceOfSupportStrategy(WorkflowSupportStrategyInterface):
    """Supports a subject that is an instance of a class, or of a class deriving from it.

    What a workflow meant for the instances of a class is added to a registry
    with — once for each class, when it is meant for several.
    """

    __slots__: tuple[str, ...] = ("_class",)

    _class: type[object]

    def __init__(self, class_: type[object]) -> None:
        """Support the instances of ``class_``."""
        self._class = class_

    @override
    def supports(self, workflow: WorkflowInterface, subject: object) -> bool:
        """Tell whether ``subject`` is an instance of the class, whatever the workflow."""
        del workflow
        return isinstance(subject, self._class)

    def get_class_name(self) -> type[object]:
        """Return the class whose instances it supports — the class itself, not its name."""
        return self._class
