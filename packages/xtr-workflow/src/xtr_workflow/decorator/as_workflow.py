"""Declaring a workflow or a state machine on a class."""

from __future__ import annotations

# Read at runtime: the dataclass below resolves its annotations from this module.
import builtins
from collections.abc import Callable, Mapping, Sequence
from dataclasses import InitVar, dataclass, field
from enum import Enum
from typing import ClassVar, TypeVar, cast, final

from xtr_workflow.exception import LogicError
from xtr_workflow.validator import DefinitionValidatorInterface
from xtr_workflow.workflow_type import WorkflowType

from ._build_event_name import NAME_PLACEHOLDER
from ._build_metadata import build_metadata
from ._resolved_listeners import resolve_listeners
from ._workflow_name import class_name, workflow_name
from .place import Place

__all__ = ["WORKFLOW_ATTRIBUTE", "AsWorkflow", "as_workflow", "workflow_declared_on"]

WORKFLOW_ATTRIBUTE = "__xtr_workflow__"
"""Where :func:`as_workflow` records its declaration on the class."""

_ClassT = TypeVar("_ClassT", bound=type)

_DECORATOR: str = "@as_workflow"


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class AsWorkflow:
    """What ``@as_workflow`` declares about the workflow a class defines.

    The transitions are the ``Transition`` markers on the class's constants;
    the places are those the transitions use, those of the ``places`` enum,
    and those a ``Place`` marker adds.

    Attributes:
        name: The name of the workflow; without it, the class's name
            snake-cased, without its ``Workflow`` or ``StateMachine`` suffix.
        type: Whether a subject is in one place at a time (a state machine)
            or in several (a workflow).
        supports: The classes of the subjects the workflow moves; without it
            nor ``support_strategy``, the workflow is not in the registry and
            is only reached by injection.
        support_strategy: The service telling which subjects the workflow
            moves.
        initial_marking: The places a subject starts in; without it, the
            places marked initial, else the first member of ``places``, else
            the first place the first transition leaves.
        marking_property: Where the subjects keep their marking; ``marking``
            without it.
        marking_store: The service keeping the subjects' markings.
        metadata: The metadata of the workflow, its description included.
        audit_trail: Whether every move is logged.
        events_to_dispatch: The events dispatched, or, each prefixed with
            ``!``, those not dispatched; every one without it.
        definition_validators: Validators run on the definition, besides the
            one of its type.
        places: The string enum listing the places: each member is a place,
            and each place must be a member.
        place_markers: The ``Place`` marker of each enum member that needs
            one, keyed by the member.
    """

    NAME_PLACEHOLDER: ClassVar[str] = NAME_PLACEHOLDER
    """Stands for the workflow's name in the events of its class's listeners, until resolved."""

    name: str | None = None
    type: WorkflowType = WorkflowType.STATE_MACHINE
    supports: builtins.type | Sequence[builtins.type] = ()
    support_strategy: str | None = None
    initial_marking: str | Enum | Sequence[str | Enum] | None = None
    marking_property: str | None = None
    marking_store: str | None = None
    description: InitVar[str | None] = None
    """The description of the workflow, kept under the ``description`` key of its metadata."""

    metadata: Mapping[str, object] = field(default_factory=dict[str, object])
    audit_trail: bool = False
    events_to_dispatch: Sequence[str] | None = None
    definition_validators: Sequence[builtins.type[DefinitionValidatorInterface]] = ()
    places: builtins.type[Enum] | None = None
    place_markers: Mapping[Enum, Place] = field(default_factory=dict[Enum, Place])

    def __post_init__(self, description: str | None) -> None:
        """Refuse arguments that contradict each other, and join the description to the metadata.

        Raises:
            LogicError: If ``supports`` comes with ``support_strategy``,
                ``marking_property`` with ``marking_store``, or a description
                with one in ``metadata``.
        """
        if self.supports and self.support_strategy is not None:
            raise LogicError(
                f'The "supports" and "support_strategy" arguments of "{_DECORATOR}" cannot be '
                "used together."
            )
        if self.marking_property is not None and self.marking_store is not None:
            raise LogicError(
                f'The "marking_property" and "marking_store" arguments of "{_DECORATOR}" cannot '
                "be used together."
            )
        object.__setattr__(self, "metadata", build_metadata(self.metadata, description, _DECORATOR))


def as_workflow(  # noqa: PLR0913 — one argument per thing a workflow declares.
    *,
    name: str | None = None,
    type: WorkflowType = WorkflowType.STATE_MACHINE,  # noqa: A002 — the declaration's own name.
    supports: builtins.type | Sequence[builtins.type] = (),
    support_strategy: str | None = None,
    initial_marking: str | Enum | Sequence[str | Enum] | None = None,
    marking_property: str | None = None,
    marking_store: str | None = None,
    description: str | None = None,
    metadata: Mapping[str, object] | None = None,
    audit_trail: bool = False,
    events_to_dispatch: Sequence[str] | None = None,
    definition_validators: Sequence[builtins.type[DefinitionValidatorInterface]] = (),
    places: builtins.type[Enum] | None = None,
    place_markers: Mapping[Enum, Place] | None = None,
) -> Callable[[_ClassT], _ClassT]:
    """Declare that the decorated class defines a workflow; the arguments are :class:`AsWorkflow`'s.

    ```python
    @as_workflow(supports=Article, marking_property="state")
    class ArticleWorkflow(WorkflowTrait):
        PUBLISH: ClassVar[Annotated[str, Transition(froms="draft", tos="published")]] = "publish"

        @as_guard_listener(transition=PUBLISH)
        def guard_publish(self, event: GuardEvent) -> None: ...
    ```

    It records the declaration on the class, for the workflow bundle to build
    the workflow from; the declaration is the class's own, so a class
    deriving it defines no workflow unless decorated too. It also makes the
    class's listeners that name no workflow listen to this one — keep it
    above every listener decorator on the class.

    Raises:
        LogicError: If arguments contradict each other, the name is empty,
            the class is already decorated, or a place marker marks no member
            of ``places``.
    """
    declaration = AsWorkflow(
        name=name,
        type=type,
        supports=supports,
        support_strategy=support_strategy,
        initial_marking=initial_marking,
        marking_property=marking_property,
        marking_store=marking_store,
        description=description,
        metadata={} if metadata is None else metadata,
        audit_trail=audit_trail,
        events_to_dispatch=events_to_dispatch,
        definition_validators=definition_validators,
        places=places,
        place_markers={} if place_markers is None else place_markers,
    )

    def decorate(class_: _ClassT) -> _ClassT:
        if WORKFLOW_ATTRIBUTE in vars(class_):
            raise LogicError(
                f'"{class_name(class_)}" cannot have several "{_DECORATOR}" decorators.'
            )

        resolved_name = workflow_name(declaration.name, class_)
        places_enum = declaration.places
        if places_enum is not None:
            for member in declaration.place_markers:
                if not isinstance(member, places_enum):
                    raise LogicError(
                        f'The place "{cast("object", member.value)}" of the workflow defined by '
                        f'"{class_name(class_)}" is not a case of "{class_name(places_enum)}".'
                    )

        resolve_listeners(class_, resolved_name)
        setattr(class_, WORKFLOW_ATTRIBUTE, declaration)
        return class_

    return decorate


def workflow_declared_on(class_: type) -> AsWorkflow | None:
    """Return the workflow ``class_`` itself declares, never one a base class declares."""
    # Only :func:`as_workflow` writes the attribute, always with an :class:`AsWorkflow`.
    return cast("AsWorkflow | None", vars(class_).get(WORKFLOW_ATTRIBUTE))
