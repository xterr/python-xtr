"""Configuration of one workflow or state machine."""

from __future__ import annotations

# Read at runtime: the dataclass below resolves its annotations from this module.
import builtins
import inspect
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, TypeAlias, cast, final

from xtr_workflow.decorator._workflow_name import class_name
from xtr_workflow.exception import InvalidArgumentError
from xtr_workflow.validator import DefinitionValidatorInterface
from xtr_workflow.workflow_events import WorkflowEvents
from xtr_workflow.workflow_type import WorkflowType

from ._place_name import place_name
from .audit_trail_config import AuditTrailConfig
from .marking_store_config import MarkingStoreConfig
from .place_config import PlaceConfig
from .transition_config import TransitionConfig

__all__ = ["WorkflowDefinitionConfig"]

_Place: TypeAlias = str | Enum | PlaceConfig
_Places: TypeAlias = _Place | Sequence[_Place] | Mapping[str, PlaceConfig | None]
_Transitions: TypeAlias = Sequence[TransitionConfig] | Mapping[str, TransitionConfig]

_EVENTS: Final = frozenset(WorkflowEvents.ALIASES.values())

# The defaults the typed signature below shows; the dataclass builds its own.
_AUDIT_TRAIL_DISABLED: Final = AuditTrailConfig()
_NO_METADATA: Final[Mapping[str, object]] = MappingProxyType({})


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowDefinitionConfig:
    """A workflow or a state machine, configured.

    Lists may be written the shortest way that says them, and are read into
    one shape: one supported class or initial place on its own; places as
    names, members of a string enum or :class:`PlaceConfig` — or keyed by
    name, a :class:`PlaceConfig` or ``None`` for each; transitions keyed by
    name. A place given by an enum member is named by its value::

        WorkflowDefinitionConfig(
            supports=Article,
            initial_marking=Status.DRAFT,
            places=tuple(Status),
            transitions={
                "publish": TransitionConfig(froms=Status.DRAFT, tos=Status.PUBLISHED),
            },
        )

    Attributes:
        audit_trail: Whether every move of a subject is logged.
        type: Whether a subject is in one place at a time or in several.
        marking_store: Where the subjects' markings are kept; the default
            store of the workflow's type without it.
        supports: The classes of the subjects the workflow moves. Without
            them nor a ``support_strategy``, the workflow is not in the
            registry, and is reached by injection only.
        definition_validators: Validators run on the definition, besides the
            one of its type; each implements
            :class:`~xtr_workflow.validator.DefinitionValidatorInterface` and
            builds with no arguments.
        support_strategy: The qualifier of the
            ``WorkflowSupportStrategyInterface`` service telling which
            subjects the workflow moves.
        initial_marking: The places a subject starts in; the first place
            without them.
        events_to_dispatch: The events dispatched besides the guard, which
            always is: every one when ``None``, none when empty, those listed,
            or — every entry prefixed with ``!`` — every one but those.
        places: The places, in order; those the transitions use are added
            after them.
        transitions: The transitions; at least one.
        metadata: The metadata of the workflow, its ``description`` included.
    """

    audit_trail: AuditTrailConfig = field(default_factory=AuditTrailConfig)
    type: WorkflowType = WorkflowType.STATE_MACHINE
    marking_store: MarkingStoreConfig | None = None
    supports: tuple[builtins.type, ...] = ()
    definition_validators: tuple[builtins.type[DefinitionValidatorInterface], ...] = ()
    support_strategy: str | None = None
    initial_marking: tuple[str, ...] = ()
    events_to_dispatch: tuple[str, ...] | None = None
    places: tuple[PlaceConfig, ...] = ()
    transitions: tuple[TransitionConfig, ...]
    metadata: Mapping[str, object] = field(default_factory=dict[str, object])

    if TYPE_CHECKING:
        # Lists may be given in every shorthand above, read into tuples by
        # ``__post_init__``; the attributes always hold the tuples.
        def __init__(  # noqa: PLR0913 — one parameter per option of a workflow.
            self,
            *,
            audit_trail: AuditTrailConfig = _AUDIT_TRAIL_DISABLED,
            type: WorkflowType = WorkflowType.STATE_MACHINE,  # noqa: A002 — the option's own name.
            marking_store: MarkingStoreConfig | None = None,
            supports: builtins.type | Sequence[builtins.type] = (),
            definition_validators: Sequence[builtins.type[DefinitionValidatorInterface]] = (),
            support_strategy: str | None = None,
            initial_marking: str | Enum | Sequence[str | Enum] = (),
            events_to_dispatch: Sequence[str] | None = None,
            places: _Places = (),
            transitions: _Transitions,
            metadata: Mapping[str, object] = _NO_METADATA,
        ) -> None:
            """Configure a workflow from its transitions, and what else it sets."""

    def __post_init__(self) -> None:
        """Read every shorthand into its tuple, and refuse what no workflow could run.

        Raises:
            InvalidArgumentError: If ``supports`` comes with
                ``support_strategy``, ``events_to_dispatch`` names an unknown
                event, mixes listed and ``!``-prefixed ones or blocks the
                guard, a definition validator is not one or needs arguments,
                there is no transition, a transition has no name or no arc
                one way, or a place has no name.
        """
        supports: object = self.supports
        object.__setattr__(
            self,
            "supports",
            (supports,) if isinstance(supports, builtins.type) else tuple(self.supports),
        )
        initial_marking: object = self.initial_marking
        object.__setattr__(
            self,
            "initial_marking",
            (place_name(initial_marking),)
            if isinstance(initial_marking, str | Enum)
            else tuple(place_name(place) for place in self.initial_marking),
        )
        object.__setattr__(self, "definition_validators", tuple(self.definition_validators))
        if self.events_to_dispatch is not None:
            object.__setattr__(self, "events_to_dispatch", tuple(self.events_to_dispatch))
        object.__setattr__(self, "places", _places(self.places))
        object.__setattr__(self, "transitions", _transitions(self.transitions))

        if self.supports and self.support_strategy is not None:
            raise InvalidArgumentError('"supports" and "support_strategy" cannot be used together.')
        _check_events_to_dispatch(self.events_to_dispatch)
        for validator in self.definition_validators:
            _check_definition_validator(validator)


def _places(places: _Places) -> tuple[PlaceConfig, ...]:
    """Return ``places`` — however written — as :class:`PlaceConfig` instances, each named.

    Raises:
        InvalidArgumentError: If a place has no name.
    """
    read: list[PlaceConfig] = []
    if isinstance(places, Mapping):
        for key, place in places.items():
            if place is None:
                read.append(PlaceConfig(key))
            else:
                read.append(place if place.name else replace(place, name=key))
    else:
        given: Sequence[_Place] = (
            (places,) if isinstance(places, str | Enum | PlaceConfig) else places
        )
        read.extend(
            place if isinstance(place, PlaceConfig) else PlaceConfig(place_name(place))
            for place in given
        )

    if any(not place.name for place in read):
        raise InvalidArgumentError('The name of a place cannot contain an empty value, but got "".')
    return tuple(read)


def _transitions(transitions: _Transitions) -> tuple[TransitionConfig, ...]:
    """Return ``transitions`` — listed or keyed by name — as one tuple, each named and connected.

    Raises:
        InvalidArgumentError: If there is no transition, or one has no name or
            no arc one way.
    """
    if isinstance(transitions, Mapping):
        read = tuple(
            transition if transition.name else replace(transition, name=key)
            for key, transition in transitions.items()
        )
    else:
        read = tuple(transitions)

    if not read:
        raise InvalidArgumentError(
            'The "transitions" option should have at least 1 element(s) defined.'
        )
    for transition in read:
        if not transition.name:
            raise InvalidArgumentError(
                'The "name" option is required for each transition in workflow configuration.'
            )
        for option, arcs in (("froms", transition.froms), ("tos", transition.tos)):
            if not arcs:
                raise InvalidArgumentError(
                    f'The "{option}" option of the transition "{transition.name}" should have at '
                    "least 1 element(s) defined."
                )
    return read


def _check_events_to_dispatch(events_to_dispatch: tuple[str, ...] | None) -> None:
    """Refuse events no workflow dispatches, a mix of listed and blocked ones, and a blocked guard.

    Raises:
        InvalidArgumentError: If ``events_to_dispatch`` cannot be followed.
    """
    if events_to_dispatch is None:
        return

    if any(entry.removeprefix("!") not in _EVENTS for entry in events_to_dispatch):
        raise InvalidArgumentError(
            'The value must be "null" or an array of workflow events (like ["workflow.enter"]). '
            'Prefix an event with "!" to disable it (e.g. ["!workflow.announce"]).'
        )
    blocked = [entry for entry in events_to_dispatch if entry.startswith("!")]
    if blocked and len(blocked) != len(events_to_dispatch):
        raise InvalidArgumentError(
            'Cannot mix allow-list and block-list entries in "events_to_dispatch": every entry '
            'must start with "!" (block-list mode) or none of them must (allow-list mode).'
        )
    if f"!{WorkflowEvents.GUARD}" in blocked:
        raise InvalidArgumentError(
            f'The "{WorkflowEvents.GUARD}" event cannot be disabled in "events_to_dispatch": it '
            "is always dispatched."
        )


def _check_definition_validator(validator: builtins.type[object]) -> None:
    """Refuse a class that is not a definition validator, or cannot be built with no arguments.

    Raises:
        InvalidArgumentError: If ``validator`` cannot be run on a definition.
    """
    if not issubclass(validator, DefinitionValidatorInterface):
        raise InvalidArgumentError(
            f'The validation class "{class_name(validator)}" is not an instance of '
            f'"{class_name(DefinitionValidatorInterface)}".'
        )
    required = [
        parameter
        for parameter in inspect.signature(validator).parameters.values()
        if cast("object", parameter.default) is inspect.Parameter.empty
        and parameter.kind not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
    ]
    if required:
        raise InvalidArgumentError(
            f'The "{class_name(validator)}" validation class constructor must not have any '
            "arguments."
        )
