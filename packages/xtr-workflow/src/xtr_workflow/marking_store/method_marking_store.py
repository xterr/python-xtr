"""Keeping a subject's marking on the subject, through its accessors or its attribute."""

from __future__ import annotations

import inspect
import sys
import types
from enum import Enum
from typing import TYPE_CHECKING, assert_never, cast, final, get_args, get_origin

from typing_extensions import override

from xtr_workflow.exception import LogicError
from xtr_workflow.marking import Marking

from ._marking_store_method import MarkingStoreMethod
from .marking_store_interface import MarkingStoreInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence
    from typing import TypeAlias

    _Getter: TypeAlias = Callable[[object], Awaitable[object]]
    _Setter: TypeAlias = Callable[[object, object, dict[str, object]], Awaitable[None]]

__all__ = ["MethodMarkingStore"]


@final
class MethodMarkingStore(MarkingStoreInterface):
    """Keeps a subject's marking on the subject itself.

    Through its ``get_<property>()`` and ``set_<property>(places, context)``
    methods when it has them — a coroutine is awaited, a plain method called,
    and a setter with no second parameter is handed the places alone — else
    through its attribute ``<property>``. A subject whose attribute was never
    set is in no place yet.

    A state machine's subject keeps the name of its one place — or, when the
    setter's first parameter or the attribute is annotated with an enum, the
    member of that value; a workflow's subject keeps a dict of the tokens each
    place holds.

    How the subjects of a class are read, and how they are written, is worked
    out from the first one met, then kept for the others.
    """

    __slots__ = ("_getters", "_marking_property", "_setters", "_single_state")

    _single_state: bool
    _marking_property: str
    _getters: dict[type[object], _Getter]
    _setters: dict[type[object], _Setter]

    def __init__(self, single_state: bool = False, marking_property: str = "marking") -> None:
        """Keep the marking in ``marking_property``.

        Args:
            single_state: Keep the name of one place rather than a dict of
                places — for a state machine, whose subject is in one place.
            marking_property: The attribute keeping the marking, which also
                names the accessors: ``get_<marking_property>()`` and
                ``set_<marking_property>()``.
        """
        self._single_state = single_state
        self._marking_property = marking_property
        self._getters = {}
        self._setters = {}

    @override
    async def get_marking(self, subject: object) -> Marking:
        """Return the marking ``subject`` keeps; empty when it keeps none yet.

        Raises:
            LogicError: If ``subject`` has neither getter nor attribute, or a
                workflow's subject keeps anything but a dict.
        """
        getter = self._getters.get(type(subject))
        if getter is None:
            getter = self._getters[type(subject)] = self._getter_of(subject)
        try:
            kept = await getter(subject)
        except AttributeError as error:
            if error.name != self._marking_property or error.obj is not subject:
                raise
            # Its attribute was never set: the subject is in no place yet.
            return Marking()

        if kept is None:
            return Marking()
        if self._single_state:
            place = cast("object", kept.value) if isinstance(kept, Enum) else kept
            return Marking({str(place): 1})
        if not isinstance(kept, dict):
            raise LogicError(
                f'The marking stored in "{type(subject).__name__}.{self._marking_property}" is '
                "not a dict and the Workflow's Marking store is instantiated with "
                "single_state=False."
            )
        return Marking(cast("dict[str, int]", kept))

    @override
    async def set_marking(
        self,
        subject: object,
        marking: Marking,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Hand ``subject`` the name of its first place, or a dict of every place.

        Args:
            subject: The object the workflow moved.
            marking: Where it is now.
            context: The context the transition ran with, handed to a setter
                declaring a second parameter.

        Raises:
            LogicError: If ``subject`` has neither setter nor attribute, or a
                state machine's setter or attribute is annotated with a name
                only the type checker imports.
        """
        places = marking.get_places()
        kept: object = next(iter(places), None) if self._single_state else places
        setter = self._setters.get(type(subject))
        if setter is None:
            setter = self._setters[type(subject)] = self._setter_of(subject)
        await setter(subject, kept, dict(context) if context is not None else {})

    def _getter_of(self, subject: object) -> _Getter:
        """Work out how the subjects of ``subject``'s class are read."""
        attribute = self._marking_property
        method = f"get_{attribute}"
        store_method = _reached_through(subject, method, attribute)
        match store_method:
            case MarkingStoreMethod.METHOD:
                awaited = inspect.iscoroutinefunction(cast("object", getattr(subject, method)))

                async def call(subject: object) -> object:
                    kept = cast("Callable[[], object]", getattr(subject, method))()
                    return await cast("Awaitable[object]", kept) if awaited else kept

                return call
            case MarkingStoreMethod.PROPERTY:

                async def read(subject: object) -> object:
                    return cast("object", getattr(subject, attribute))

                return read
            case _:
                # A way of reaching a subject added without a getter fails here.
                assert_never(store_method)

    def _setter_of(self, subject: object) -> _Setter:
        """Work out how the subjects of ``subject``'s class are written."""
        attribute = self._marking_property
        method = f"set_{attribute}"
        store_method = _reached_through(subject, method, attribute)
        match store_method:
            case MarkingStoreMethod.METHOD:
                return self._method_setter(subject, method)
            case MarkingStoreMethod.PROPERTY:
                return self._attribute_setter(subject, attribute)
            case _:
                # A way of reaching a subject added without a setter fails here.
                assert_never(store_method)

    def _method_setter(self, subject: object, method: str) -> _Setter:
        """Write through ``method``, handing it the context when it has room for it."""
        accessor = cast("Callable[..., object]", getattr(subject, method))
        parameters = list(inspect.signature(accessor).parameters.values())
        function = cast("object", inspect.unwrap(accessor))
        enum_type = self._enum_type(
            cast("object", parameters[0].annotation) if parameters else None,
            cast("dict[str, object]", getattr(function, "__globals__", {})),
            f'the first parameter of "{type(subject).__name__}.{method}()"',
        )
        awaited = inspect.iscoroutinefunction(accessor)
        with_context = _has_room_for_context(parameters)

        async def call(subject: object, kept: object, context: dict[str, object]) -> None:
            value = enum_type(kept) if enum_type is not None else kept
            arguments = (value, context) if with_context else (value,)
            written = cast("Callable[..., object]", getattr(subject, method))(*arguments)
            if awaited:
                _ = await cast("Awaitable[object]", written)

        return call

    def _attribute_setter(self, subject: object, attribute: str) -> _Setter:
        """Write ``attribute`` itself, which keeps the places alone, never the context."""
        declaring = _declaring(type(subject), attribute)
        enum_type = (
            self._enum_type(
                cast("object", inspect.get_annotations(declaring)[attribute]),
                cast(
                    "dict[str, object]",
                    getattr(sys.modules.get(declaring.__module__), "__dict__", {}),
                ),
                f'"{type(subject).__name__}.{attribute}"',
            )
            if declaring is not None
            else None
        )

        async def assign(subject: object, kept: object, _context: dict[str, object]) -> None:
            setattr(subject, attribute, enum_type(kept) if enum_type is not None else kept)

        return assign

    def _enum_type(
        self, annotation: object, namespace: dict[str, object], label: str
    ) -> type[Enum] | None:
        """Return the enum a state machine's place is written as, or ``None`` to write it as is.

        A workflow's subject is handed a dict, which no enum member stands
        for, so its annotation is not read at all.
        """
        if not self._single_state:
            return None
        return _enum_named_by(_evaluated(annotation, namespace, label))


def _reached_through(subject: object, method: str, attribute: str) -> MarkingStoreMethod:
    """Tell whether ``subject`` is reached through ``method``, else through ``attribute``.

    The attribute counts when the subject holds it, when its class defines it
    — a default, a slot, a property — or when a class of its own declares it
    with an annotation, set or not.

    Raises:
        LogicError: If ``subject`` has neither.
    """
    subject_type = type(subject)
    if callable(getattr(subject_type, method, None)):
        return MarkingStoreMethod.METHOD
    if (
        hasattr(subject, attribute)
        or hasattr(subject_type, attribute)
        or _declaring(subject_type, attribute) is not None
    ):
        return MarkingStoreMethod.PROPERTY
    raise LogicError(
        f'Cannot store marking: class "{subject_type.__name__}" should have either a public '
        f'method named "{method}()" or a public property named "{attribute}"; none found.'
    )


def _declaring(subject_type: type[object], attribute: str) -> type[object] | None:
    """Return the first class of ``subject_type``'s ancestry annotating ``attribute``."""
    return next(
        (owner for owner in subject_type.__mro__ if attribute in inspect.get_annotations(owner)),
        None,
    )


def _has_room_for_context(parameters: Sequence[inspect.Parameter]) -> bool:
    """Tell whether a setter taking ``parameters`` takes a second argument by position."""
    positional = [p for p in parameters if p.kind in {p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD}]
    return len(positional) > 1 or any(p.kind is p.VAR_POSITIONAL for p in parameters)


def _evaluated(annotation: object, namespace: dict[str, object], label: str) -> object:
    """Return ``annotation``, or what its source names when its evaluation was postponed.

    Read alone, in the module that wrote it, the way ``typing.get_type_hints``
    reads each annotation of an object — so no other annotation of the subject
    has to be readable at runtime.

    Raises:
        LogicError: If it names what its module imports only for the type checker.
    """
    if not isinstance(annotation, str):
        return annotation
    try:
        return cast("object", eval(annotation, namespace))  # noqa: S307 — the subject's own annotation, read as typing.get_type_hints reads one
    except NameError as error:
        raise LogicError(
            f"Cannot store marking: the annotation of {label} cannot be read at runtime "
            f"({error}); import what it names outside TYPE_CHECKING."
        ) from error


def _enum_named_by(annotation: object) -> type[Enum] | None:
    """Return the enum ``annotation`` names, on its own or or-ed with ``None``."""
    origin = cast("object", get_origin(annotation))
    # ``A | None``, and the ``Optional[A]`` spelling, which has an origin of its own before 3.14.
    union = origin is types.UnionType or repr(origin) == "typing.Union"
    members = cast("tuple[object, ...]", get_args(annotation)) if union else (annotation,)
    match [member for member in members if member is not type(None)]:
        case [type() as named] if issubclass(named, Enum):
            return named
        case _:
            return None
