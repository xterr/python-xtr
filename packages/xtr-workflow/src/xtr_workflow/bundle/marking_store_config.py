"""Configuration of where a configured workflow keeps its subjects' markings."""

from __future__ import annotations

# Read at runtime: the dataclass below resolves its annotations from this module.
from dataclasses import dataclass
from typing import Literal, final

from xtr_workflow.exception import InvalidArgumentError

__all__ = ["MarkingStoreConfig"]


@final
@dataclass(frozen=True, slots=True)
class MarkingStoreConfig:
    """Where a workflow keeps the marking of each subject.

    A ``type`` or a ``property`` makes the workflow keep the marking on the
    subject itself, through a
    :class:`~xtr_workflow.marking_store.MethodMarkingStore` reading and writing
    ``property`` — ``marking`` without one — holding one place for a state
    machine and several for a workflow. Without either, ``service`` names the
    store; with nothing set at all, the workflow keeps the default store of
    its type.

    Attributes:
        type: ``"method"``, the only store the workflow builds itself.
        property: The name of the subject's attribute, or of its
            ``get_<property>`` / ``set_<property>`` methods.
        service: The qualifier of the ``MarkingStoreInterface`` service to
            use instead.
    """

    type: Literal["method"] | None = None
    property: str | None = None
    service: str | None = None

    def __post_init__(self) -> None:
        """Refuse a store the workflow cannot build, and an empty name.

        Raises:
            InvalidArgumentError: If ``type`` is not ``"method"``, or
                ``property`` or ``service`` is empty.
        """
        if self.type is not None and self.type != "method":
            raise InvalidArgumentError(
                f'The value "{self.type}" is not allowed for the marking store type. '
                'Permissible values: "method".'
            )
        for option, value in (("property", self.property), ("service", self.service)):
            if value == "":
                raise InvalidArgumentError(
                    f'The marking store {option} cannot contain an empty value, but got "".'
                )
