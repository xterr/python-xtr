"""Configuration of the workflow bundle."""

from __future__ import annotations

# Read at runtime: the dataclass below resolves its annotations from this module.
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import final

from xtr_workflow.exception import InvalidArgumentError

from .workflow_definition_config import WorkflowDefinitionConfig

__all__ = ["WorkflowConfig"]


@final
@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    """The workflows and state machines the bundle registers, keyed by name.

    Buildable with no arguments: activating the bundle with no workflow
    configured registers only those declared with ``@as_workflow``.

    ```python
    WorkflowConfig(
        workflows={
            "blog_publishing": WorkflowDefinitionConfig(
                supports=Article,
                marking_store=MarkingStoreConfig(property="status"),
                transitions={
                    "publish": TransitionConfig(froms="draft", tos="published"),
                },
            ),
        },
    )
    ```

    Attributes:
        workflows: Each workflow's configuration, keyed by its name.
    """

    workflows: Mapping[str, WorkflowDefinitionConfig] = field(
        default_factory=dict[str, WorkflowDefinitionConfig]
    )

    def __post_init__(self) -> None:
        """Refuse a workflow that is not configured by a :class:`WorkflowDefinitionConfig`.

        Raises:
            InvalidArgumentError: If a workflow is configured by anything else.
        """
        for name, workflow in self.workflows.items():
            if not isinstance(workflow, WorkflowDefinitionConfig):  # pyright: ignore[reportUnnecessaryIsInstance] -- configuration is written by hand; the annotation is not enforced
                raise InvalidArgumentError(
                    f'Invalid type for path "workflow.workflows.{name}". Expected '
                    f'"WorkflowDefinitionConfig", but got "{type(workflow).__name__}".'
                )
