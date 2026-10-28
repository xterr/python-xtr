"""Reading the constants a workflow class annotates, with the markers each carries.

Each annotation is evaluated on its own, as ``typing.get_type_hints`` evaluates
each annotation of a class, so one naming what its module imports only for the
type checker — the class of a collaborator the workflow class keeps, say — does
not keep the others from being read. Such an annotation carries no marker,
unless its source shows it does: then the class cannot be read.
"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Mapping
from typing import ClassVar, Final, NamedTuple, cast, get_args, get_origin

from xtr_workflow.decorator._workflow_name import class_name
from xtr_workflow.exception import LogicError

if sys.version_info >= (3, 14):
    import annotationlib  # pyright: ignore[reportUnreachable] -- checked as 3.11, run from 3.14 on

__all__ = ["MarkedConstant", "marked_constants"]

_MARKER_SIGNS: Final = ("Annotated", "Transition(", "Place(")
"""What the source of an annotation carrying markers shows: markers go inside ``Annotated``."""


class MarkedConstant(NamedTuple):
    """A class constant carrying markers."""

    attribute: str
    """Its name on the class."""

    label: str
    """How errors name it: the class declaring it, then its name."""

    markers: tuple[object, ...]
    """The metadata of its ``Annotated`` annotation."""


class _Unreadable(NamedTuple):
    """An annotation that cannot be evaluated at runtime."""

    source: str
    """What it was written as."""

    error: NameError
    """Why it cannot be evaluated: the name it needs and its module lacks."""


def marked_constants(class_: type) -> list[MarkedConstant]:
    """Return each annotated constant of ``class_`` and of its bases, with its markers.

    The class's own constants come first, then those it inherits.

    Raises:
        LogicError: If an annotation whose source shows markers cannot be
            evaluated at runtime: it names what its module imports only for
            the type checker.
    """
    found: list[MarkedConstant] = []
    seen: set[str] = set()
    for owner in class_.__mro__[:-1]:
        for attribute, annotation in _annotations(owner).items():
            if attribute in seen:
                continue
            seen.add(attribute)
            label = f"{class_name(owner)}.{attribute}"
            found.append(MarkedConstant(attribute, label, _markers(annotation, label)))
    return found


if sys.version_info >= (3, 14):

    def _annotations(owner: type) -> dict[str, object]:  # pyright: ignore[reportUnreachable] -- checked as 3.11, run from 3.14 on
        """Return the annotations ``owner`` declares itself, each evaluated on its own.

        One that cannot be evaluated is an ``_Unreadable`` in its place.
        """
        try:
            declared = annotationlib.get_annotations(owner)
        except NameError:
            return _deferred_annotations(owner)
        return _each_evaluated(owner, declared)

    def _deferred_annotations(owner: type) -> dict[str, object]:
        """Return the annotations ``owner`` defers, of which some cannot be evaluated.

        A module not importing ``annotations`` from ``__future__`` defers them,
        and reading them evaluates them all at once, failing on the first that
        cannot be. Each is evaluated as far as it can be instead; whether it
        can be in full is told by evaluating alone the source it was written
        as, since a name it lacks may hide deep in what was evaluated — in a
        marker's places, say.
        """
        values = cast(
            "dict[str, object]",
            annotationlib.get_annotations(owner, format=annotationlib.Format.FORWARDREF),
        )
        sources = annotationlib.get_annotations(owner, format=annotationlib.Format.STRING)
        read: dict[str, object] = {}
        for attribute, value in values.items():
            try:
                evaluated = _evaluated(owner, sources[attribute])
            except SyntaxError:
                # Its source holds a value no source stands for, such as a lambda:
                # it tells nothing, and what was evaluated is read as is.
                evaluated = value
            read[attribute] = evaluated if isinstance(evaluated, _Unreadable) else value
        return read

else:

    def _annotations(owner: type) -> dict[str, object]:
        """Return the annotations ``owner`` declares itself, each evaluated on its own.

        One that cannot be evaluated is an ``_Unreadable`` in its place.
        """
        return _each_evaluated(owner, inspect.get_annotations(owner))


def _each_evaluated(owner: type, declared: Mapping[str, object]) -> dict[str, object]:
    """Return the annotations ``owner`` declares, each written as a string evaluated alone."""
    return {
        attribute: _evaluated(owner, annotation) if isinstance(annotation, str) else annotation
        for attribute, annotation in declared.items()
    }


def _evaluated(owner: type, source: str) -> object:
    """Return the annotation ``source`` of ``owner`` evaluated alone, or an ``_Unreadable``.

    Evaluated as ``typing.get_type_hints`` evaluates each annotation of a
    class: with the names of the class's module first, then the class's own.
    """
    module = cast("dict[str, object]", getattr(sys.modules.get(owner.__module__), "__dict__", {}))
    try:
        return cast("object", eval(source, dict(vars(owner)), module))  # noqa: S307 — the class's own annotation, read as typing.get_type_hints reads one
    except NameError as error:
        return _Unreadable(source, error)


def _markers(annotation: object, label: str) -> tuple[object, ...]:
    """Return the markers of the annotation of the constant ``label`` names.

    One that cannot be evaluated carries none, unless its source shows it does.

    Raises:
        LogicError: If it cannot be evaluated and its source shows markers.
    """
    if not isinstance(annotation, _Unreadable):
        return _annotated_markers(annotation)
    if not any(sign in annotation.source for sign in _MARKER_SIGNS):
        return ()
    raise LogicError(
        f'The annotation of "{label}" cannot be read at runtime ({annotation.error}); import what '
        "it names outside TYPE_CHECKING."
    ) from annotation.error


def _annotated_markers(hint: object) -> tuple[object, ...]:
    """Return the ``Annotated`` metadata of a constant's annotation, ``ClassVar`` unwrapped."""
    if get_origin(hint) is ClassVar:
        hint = cast("object", get_args(hint)[0])
    return cast("tuple[object, ...]", getattr(hint, "__metadata__", ()))
