"""Narrowing the listeners of a workflow class to the workflow it declares.

A listener decorator that names a place or transition but no workflow cannot
know which workflow it means, and one that names neither cannot tell "every
workflow" from "this class's workflow": both are settled here, when
``@as_workflow`` decorates the class and its workflow's name is known. What
the event dispatcher then reads are ordinary, fully named declarations.
"""

from __future__ import annotations

import functools
import inspect
from dataclasses import replace
from typing import TYPE_CHECKING, Final, cast

from xtr_event_dispatcher.decorator.event_listener_declaration import (
    LISTENERS_ATTRIBUTE,
    recorded_on,
)

from ._build_event_name import NAME_PLACEHOLDER
from .workflow_listener_declaration import workflow_listeners_recorded_on

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_event_dispatcher.decorator import EventListenerDeclaration

__all__ = ["resolve_listeners"]

_UNRESOLVED_ATTRIBUTE: Final = "__xtr_workflow_unresolved_listeners__"
"""Where a function resolved in place keeps the declarations it was written with."""

_PLACEHOLDER_PREFIX: Final = f"workflow.{NAME_PLACEHOLDER}."
_PREFIX: Final = "workflow."


def resolve_listeners(class_: type, workflow_name: str) -> None:
    """Make the listeners of ``class_`` that name no workflow listen to ``workflow_name``.

    A declaration naming a place or transition without a workflow, and one a
    workflow listener decorator made naming neither, are narrowed; one naming
    a workflow, and a plain ``@as_event_listener("workflow.guard")``, are
    left as they are.

    The class's own declarations and those on the methods written in its body
    are replaced in place. An inherited method is shared with the base and
    every other class deriving it, so it is overridden on ``class_`` by a
    method calling it, carrying the narrowed declarations: two workflow
    classes deriving one base each listen to their own workflow. The event
    dispatcher reads a method's declarations from the first class defining
    it, so the override carries every declaration of the method; it keeps
    the method's signature, which the dispatcher reads the event from.
    """
    own = recorded_on(class_)
    resolved_own = _resolved(own, class_, workflow_name)
    if resolved_own != own:
        setattr(class_, LISTENERS_ATTRIBUTE, resolved_own)

    seen: set[str] = set()
    for klass in class_.__mro__[:-1]:
        for name, member in tuple(cast("Mapping[str, object]", vars(klass)).items()):
            if name in seen:
                continue
            seen.add(name)
            function = _function_of(member)
            if not inspect.isfunction(function):
                continue

            unresolved = _unresolved(function)
            resolved = _resolved(unresolved, function, workflow_name)
            if resolved == recorded_on(function):
                continue

            if klass is class_:
                # ``unresolved`` is what was kept, if anything was: rewriting it changes nothing.
                setattr(function, _UNRESOLVED_ATTRIBUTE, unresolved)
                setattr(function, LISTENERS_ATTRIBUTE, resolved)
                continue

            delegate = _delegate(cast("Callable[..., object]", function), class_, name)
            setattr(delegate, _UNRESOLVED_ATTRIBUTE, unresolved)
            setattr(delegate, LISTENERS_ATTRIBUTE, resolved)
            setattr(class_, name, _bound_like(member, delegate))


def _unresolved(function: Callable[..., object]) -> tuple[EventListenerDeclaration, ...]:
    """Return the declarations ``function`` was written with, before any class narrowed them."""
    kept = cast(
        "tuple[EventListenerDeclaration, ...] | None",
        getattr(function, _UNRESOLVED_ATTRIBUTE, None),
    )
    return recorded_on(function) if kept is None else kept


def _function_of(member: object) -> object:
    """Return the function a static or class method wraps, or ``member`` itself."""
    if isinstance(member, staticmethod | classmethod):
        return cast("object", member.__func__)
    return member


def _resolved(
    declarations: tuple[EventListenerDeclaration, ...], marked_on: object, workflow_name: str
) -> tuple[EventListenerDeclaration, ...]:
    """Return ``declarations`` narrowed to ``workflow_name``, given the marks on ``marked_on``."""
    marked = tuple(mark.declaration for mark in workflow_listeners_recorded_on(marked_on))
    return tuple(_narrowed(declaration, marked, workflow_name) for declaration in declarations)


def _narrowed(
    declaration: EventListenerDeclaration,
    marked: tuple[EventListenerDeclaration, ...],
    workflow_name: str,
) -> EventListenerDeclaration:
    event = declaration.event
    if not isinstance(event, str):
        return declaration

    if event.startswith(_PLACEHOLDER_PREFIX):
        node = event.removeprefix(_PLACEHOLDER_PREFIX)
        return replace(declaration, event=f"workflow.{workflow_name}.{node}")

    # ``workflow.<event>``, from a workflow listener decorator naming nothing.
    if event.count(".") == 1 and declaration in marked:
        keyword = event.removeprefix(_PREFIX)
        return replace(declaration, event=f"workflow.{workflow_name}.{keyword}")

    return declaration


def _delegate(function: Callable[..., object], class_: type, name: str) -> Callable[..., object]:
    """Return a function calling ``function``, named as a method of ``class_``.

    ``functools.wraps`` points it at ``function``, so its signature and its
    type hints — resolved in ``function``'s module — are ``function``'s.
    """

    @functools.wraps(function)
    def delegate(*args: object, **kwargs: object) -> object:
        return function(*args, **kwargs)

    delegate.__module__ = class_.__module__
    delegate.__qualname__ = f"{class_.__qualname__}.{name}"
    return delegate


def _bound_like(member: object, delegate: Callable[..., object]) -> object:
    """Wrap ``delegate`` the way ``member`` wraps its function, so it binds the same way."""
    match member:
        case staticmethod():
            return staticmethod(delegate)
        case classmethod():
            return classmethod(delegate)
        case _:
            return delegate
