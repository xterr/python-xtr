"""Reading the workflow a class declares with ``@as_workflow`` into its configuration.

The configuration it returns is checked as one written by hand is, by
:class:`WorkflowDefinitionConfig` itself.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from enum import Enum
from typing import ClassVar, Final, NamedTuple, cast, final, get_args, get_origin, get_type_hints

from xtr_workflow.arc import Arc
from xtr_workflow.decorator._workflow_name import class_name
from xtr_workflow.decorator.as_workflow import AsWorkflow
from xtr_workflow.decorator.place import Place
from xtr_workflow.decorator.transition import Transition
from xtr_workflow.exception import LogicError
from xtr_workflow.workflow_type import WorkflowType

from .arc_config import ArcConfig
from .audit_trail_config import AuditTrailConfig
from .marking_store_config import MarkingStoreConfig
from .place_config import PlaceConfig
from .transition_config import TransitionConfig
from .workflow_definition_config import WorkflowDefinitionConfig

__all__ = ["read_declaration"]

_DECORATOR: Final = "@as_workflow"


class _Constant(NamedTuple):
    """A class constant carrying markers."""

    attribute: str
    """Its name on the class."""

    label: str
    """How errors name it: the class declaring it, then its name."""

    markers: tuple[object, ...]
    """The metadata of its ``Annotated`` annotation."""


def read_declaration(class_: type, declaration: AsWorkflow) -> WorkflowDefinitionConfig:
    """Return the configuration of the workflow ``declaration`` declares on ``class_``.

    The places are those of the ``places`` enum, then those the transitions
    use, then those only a ``Place`` marker names. The initial marking is the
    declared one, else the places marked initial — on a class constant, or
    through ``place_markers`` for a member of an enum the workflow uses;
    without either, the definition starts in its first place.

    Raises:
        LogicError: If the declaration cannot be read into a workflow: a
            constant naming a transition or a place holds no name, a place is
            not a string or a member of a string enum, a state machine's
            transition has several places one way, a place is declared twice
            or is not a member of the ``places`` enum.
        InvalidArgumentError: If the configuration read is invalid, as one
            written by hand would be.
    """
    return _Reader(class_, declaration).config()


@final
class _Reader:
    """Reads one class's declaration, keeping the enums its places come from."""

    __slots__ = ("_class", "_declaration", "_enums")

    def __init__(self, class_: type, declaration: AsWorkflow) -> None:
        self._class = class_
        self._declaration = declaration
        # The enums the places come from, whose ``place_markers`` apply.
        self._enums: dict[type[Enum], None] = {}

    def config(self) -> WorkflowDefinitionConfig:
        """Return the configuration of the workflow the class declares."""
        places_enum = self._places_enum()
        # Each place's name, with the ``Place`` marker of its constant, if any.
        places: dict[str, Place | None] = {
            self._place_name(member): None for member in places_enum or ()
        }

        transitions: list[TransitionConfig] = []
        place_constants: dict[str, tuple[str, Place]] = {}
        for constant in self._constants():
            transitions.extend(
                self._transition(constant, marker)
                for marker in constant.markers
                if isinstance(marker, Transition)
            )
            self._read_place_constant(constant, place_constants)

        for transition in transitions:
            for arc in (*transition.froms, *transition.tos):
                _ = places.setdefault(arc.place, None)
        # No place has a marker yet: each place constant names a place only once.
        for name, (_, marker) in place_constants.items():
            places[name] = marker

        return self._definition(self._place_configs(places, places_enum), tuple(transitions))

    def _place_configs(
        self, places: dict[str, Place | None], places_enum: type[Enum] | None
    ) -> list[tuple[PlaceConfig, bool]]:
        """Return each place's configuration, and whether a marker makes it initial."""
        read: list[tuple[PlaceConfig, bool]] = []
        for name, constant_marker in places.items():
            if places_enum is not None and name not in _values(places_enum):
                raise LogicError(
                    f'The place "{name}" of the workflow defined by "{class_name(self._class)}" '
                    f'is not a case of "{class_name(places_enum)}".'
                )
            member_marker = self._member_marker(name)
            metadata = (constant_marker.metadata if constant_marker is not None else {}) or (
                member_marker.metadata if member_marker is not None else {}
            )
            initial = any(
                marker is not None and marker.initial for marker in (constant_marker, member_marker)
            )
            read.append((PlaceConfig(name, metadata), initial))
        return read

    def _definition(
        self, places: list[tuple[PlaceConfig, bool]], transitions: tuple[TransitionConfig, ...]
    ) -> WorkflowDefinitionConfig:
        declaration = self._declaration
        marking_store = None
        if declaration.marking_property is not None:
            marking_store = MarkingStoreConfig(property=declaration.marking_property)
        elif declaration.marking_store is not None:
            marking_store = MarkingStoreConfig(service=declaration.marking_store)

        return WorkflowDefinitionConfig(
            type=declaration.type,
            supports=declaration.supports,
            initial_marking=(
                tuple(place.name for place, initial in places if initial)
                if declaration.initial_marking is None
                else declaration.initial_marking
            ),
            metadata=declaration.metadata,
            audit_trail=AuditTrailConfig(enabled=declaration.audit_trail),
            definition_validators=declaration.definition_validators,
            places=tuple(place for place, _ in places),
            transitions=transitions,
            support_strategy=declaration.support_strategy,
            marking_store=marking_store,
            events_to_dispatch=declaration.events_to_dispatch,
        )

    def _places_enum(self) -> type[Enum] | None:
        places_enum = self._declaration.places
        if places_enum is None:
            return None
        if not (isinstance(places_enum, type) and issubclass(places_enum, Enum)):  # pyright: ignore[reportUnnecessaryIsInstance] -- the decorator's argument is not checked at runtime
            raise LogicError(
                f'The "places" argument of "{_DECORATOR}" on "{class_name(self._class)}" must be '
                f'a string-backed enum, "{class_name(places_enum)}" given.'
            )
        return places_enum

    def _constants(self) -> list[_Constant]:
        """Return each annotated constant of the class and of its bases, with its markers.

        The class's own constants come first, then those it inherits.
        """
        found: list[_Constant] = []
        seen: set[str] = set()
        for owner in self._class.__mro__[:-1]:
            hints = get_type_hints(owner, include_extras=True)
            for attribute in inspect.get_annotations(owner):
                if attribute in seen:
                    continue
                seen.add(attribute)
                found.append(
                    _Constant(
                        attribute,
                        f"{class_name(owner)}.{attribute}",
                        _annotated_markers(cast("object", hints[attribute])),
                    )
                )
        return found

    def _transition(self, constant: _Constant, marker: Transition) -> TransitionConfig:
        name = self._value(constant)
        if not isinstance(name, str):
            raise LogicError(
                f'The value of "{constant.label}" must be a string to be used as the name of a '
                f'transition, "{type(name).__name__}" given.'
            )
        transition = TransitionConfig(
            name,
            self._arcs(marker.froms, name),
            self._arcs(marker.tos, name),
            guard=marker.guard,
            metadata=marker.metadata,
        )
        if self._declaration.type is WorkflowType.STATE_MACHINE and (
            len(transition.froms) > 1 or len(transition.tos) > 1
        ):
            raise LogicError(
                f'The "{name}" transition of the state machine defined by '
                f'"{class_name(self._class)}" must have exactly one input and one output place; '
                'repeat the "Transition" marker to define several transitions with the same name.'
            )
        return transition

    def _arcs(
        self, places: str | Enum | Arc | Sequence[str | Enum | Arc], transition: str
    ) -> tuple[ArcConfig, ...]:
        # Typed loosely: the marker's arguments are not checked at runtime.
        given = cast(
            "Sequence[object]", (places,) if isinstance(places, str | Enum | Arc) else places
        )
        arcs: list[ArcConfig] = []
        for place in given:
            match place:
                case Arc():
                    arcs.append(ArcConfig(place.place, place.weight))
                case str() | Enum():
                    arcs.append(ArcConfig(self._place_name(place)))
                case _:
                    raise LogicError(
                        f'The places of the "{transition}" transition of the workflow defined by '
                        f'"{class_name(self._class)}" must be "{class_name(Arc)}" instances, enum '
                        f'cases or strings, "{type(place).__name__}" given.'
                    )
        return tuple(arcs)

    def _read_place_constant(
        self, constant: _Constant, place_constants: dict[str, tuple[str, Place]]
    ) -> None:
        place_markers = [marker for marker in constant.markers if isinstance(marker, Place)]
        if len(place_markers) > 1:
            raise LogicError(f'"{constant.label}" cannot have several "Place" markers.')
        if not place_markers:
            return

        value = self._value(constant)
        if not isinstance(value, str | Enum):
            raise LogicError(
                f'The value of "{constant.label}" must be a string or a string-backed enum case '
                f'to be used as the name of a place, "{type(value).__name__}" given.'
            )
        name = self._place_name(value)
        if name in place_constants:
            raise LogicError(
                f'The place "{name}" of the workflow defined by "{class_name(self._class)}" is '
                f'defined by both "{place_constants[name][0]}" and "{constant.label}".'
            )
        place_constants[name] = (constant.label, place_markers[0])

    def _value(self, constant: _Constant) -> object:
        # A constant annotated but never assigned holds nothing, reported as ``None``.
        return cast("object", getattr(self._class, constant.attribute, None))

    def _place_name(self, place: str | Enum) -> str:
        if not isinstance(place, Enum):
            return place
        value = cast("object", place.value)
        if not isinstance(value, str):
            raise LogicError(
                "Only string-backed enums can be used as places of the workflow defined by "
                f'"{class_name(self._class)}", "{class_name(type(place))}" is not.'
            )
        self._enums[type(place)] = None
        return value

    def _member_marker(self, place: str) -> Place | None:
        """Return the ``place_markers`` entry of the member, of an enum used, naming ``place``."""
        for enum in self._enums:
            for member in enum:
                if cast("object", member.value) == place:
                    return self._declaration.place_markers.get(member)
        return None


def _values(enum: type[Enum]) -> set[object]:
    return {cast("object", member.value) for member in enum}


def _annotated_markers(hint: object) -> tuple[object, ...]:
    """Return the ``Annotated`` metadata of a constant's annotation, ``ClassVar`` unwrapped."""
    if get_origin(hint) is ClassVar:
        hint = cast("object", get_args(hint)[0])
    return cast("tuple[object, ...]", getattr(hint, "__metadata__", ()))
