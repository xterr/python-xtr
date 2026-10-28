"""Marking a transition of a workflow declared on a class.

The class shares its name with :class:`xtr_workflow.Transition`, the
transition a definition is built from; import it as
``from xtr_workflow.decorator import Transition`` where a workflow is
declared.
"""

from __future__ import annotations

# Read at runtime: the dataclass below resolves its annotations from this module.
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import InitVar, dataclass, field
from enum import Enum
from typing import TypeAlias, final

from xtr_workflow.arc import Arc
from xtr_workflow.event_listener.guard_context import GuardContext

from ._build_metadata import build_metadata

__all__ = ["Transition"]

_Places: TypeAlias = str | Enum | Arc | Sequence[str | Enum | Arc]


@final
@dataclass(frozen=True, slots=True)
class Transition:
    """A transition of a workflow declared with ``@as_workflow``.

    Put it on a class constant valued with the transition's name:
    ``PUBLISH: ClassVar[Annotated[str, Transition(froms="draft", tos="published")]]
    = "publish"``. Repeat it in the same ``Annotated`` to declare several
    transitions of that name; a transition of a state machine has exactly one
    place in and one place out.

    Attributes:
        froms: The places the transition leaves: names, members of a string
            enum, or :class:`~xtr_workflow.Arc` to weigh one — on their own or
            in a sequence.
        tos: The places the transition enters, given the same way.
        guard: Called with the guard context — the subject, the security
            token and what to check it with; the transition is enabled only
            when it returns true, or an awaitable resolving to true.
        metadata: The metadata of the transition, its description included.
    """

    froms: _Places
    tos: _Places
    description: InitVar[str | None] = None
    """The description of the transition, kept under the ``description`` key of its metadata."""

    guard: Callable[[GuardContext], bool | Awaitable[bool]] | None = None
    metadata: Mapping[str, object] = field(default_factory=dict[str, object])

    def __post_init__(self, description: str | None) -> None:
        """Join ``description`` to the metadata.

        Raises:
            LogicError: If the metadata has a description of its own.
        """
        object.__setattr__(
            self, "metadata", build_metadata(self.metadata, description, "Transition")
        )
