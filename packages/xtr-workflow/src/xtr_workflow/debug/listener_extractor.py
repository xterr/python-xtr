"""Listing who listens to each step of a workflow, named after the code they run."""

from __future__ import annotations

import inspect
import sys
from typing import TYPE_CHECKING, Final, Protocol, cast, final

from xtr_event_dispatcher import LazyListener
from xtr_event_dispatcher.debug import WrappedListener

from xtr_workflow.exception import LogicError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from xtr_event_dispatcher_contracts import Listener, ListenerIntrospectionInterface

    from xtr_workflow.definition import Definition
    from xtr_workflow.event_listener.guard_listener import GuardListener
    from xtr_workflow.transition import Transition

__all__ = ["ListenerExtractor"]

_PLACE_STEPS: Final = ("leave", "enter", "entered")
"""The steps of a place: a subject leaving it, entering it, and having entered it."""

_TRANSITION_STEPS: Final = ("guard", "transition", "completed", "announce")
"""The steps of a transition, from being guarded to announcing what is enabled after it."""

_GUARD_LISTENER_MODULE: Final = "xtr_workflow.event_listener.guard_listener"
"""The module defining the guard listener, which is looked up and never imported here."""

_UNIT_OF_WORK_GUARD_LISTENER_MODULE: Final = "xtr_workflow.bundle._unit_of_work_guard_listener"
"""The module defining what runs a guard listener in each unit of work, looked up the same way."""


class _GuardListenerOfEachUnitOfWork(Protocol):
    """Runs a guard listener built for each unit of work."""

    async def get_guard_names(self, event_name: str, transition: Transition) -> list[str]:
        """Return the name of each guard run for ``transition``, named in a unit of work."""
        ...


@final
class ListenerExtractor:
    """Lists who listens to each step of a workflow, place by place and transition by transition.

    What a tool drawing a workflow shows beside its places and transitions:
    for each place, the listeners of its ``leave``, ``enter`` and ``entered``
    events; for each transition, those of its ``guard``, ``transition``,
    ``completed`` and ``announce`` events — every event under each of its
    three names: for every workflow, for this one, and for the place or the
    transition.

    A listener is summarised by a ``title`` naming the code it runs and the
    ``file`` that code starts in, as ``<path>:<line>`` — ``None`` when what
    runs is no function written in Python, as a built-in or a class; a guard
    listener's adds, under ``guardExpressions``, the names of the guards it
    runs for the transition.

    A listener is named after what it runs, never after a wrapper: a traced
    listener is unwrapped, a lazy one built, as dispatching to it would build
    it — which is why listing is a coroutine — and a guard listener run in
    each unit of work is named after the guard listener it runs, whose
    guards it names in a unit of work.
    """

    __slots__: tuple[str, ...] = ("_dispatcher",)

    _dispatcher: ListenerIntrospectionInterface

    def __init__(self, dispatcher: ListenerIntrospectionInterface) -> None:
        """List the listeners ``dispatcher`` runs."""
        self._dispatcher = dispatcher

    async def extract_listeners(
        self, workflow_name: str, definition: Definition
    ) -> dict[str, dict[str, list[dict[str, object]]]]:
        """Return who listens to each place and each transition of a workflow.

        Args:
            workflow_name: The name of the workflow, which its events are
                narrowed to.
            definition: Its places and transitions.

        Returns:
            Under ``"place__<place>"`` and ``"transition__<position>"`` — the
            transition's position in the definition, from 0 — the summary of
            each listener of every event, in the order they run. An event, a
            place or a transition nobody listens to is left out.

        Raises:
            LogicError: If a guard listener listens to a place's event, where
                there is no transition to name the guards of.
        """
        listeners: dict[str, dict[str, list[dict[str, object]]]] = {}
        for place in definition.get_places():
            event_names = _event_names(workflow_name, _PLACE_STEPS, place)
            described = await self._described(event_names, None)
            if described:
                listeners[f"place__{place}"] = described

        for position, transition in enumerate(definition.get_transitions()):
            event_names = _event_names(workflow_name, _TRANSITION_STEPS, transition.get_name())
            described = await self._described(event_names, transition)
            if described:
                listeners[f"transition__{position}"] = described

        return listeners

    async def _described(
        self, event_names: Iterable[str], transition: Transition | None
    ) -> dict[str, list[dict[str, object]]]:
        """Return the summary of every listener of ``event_names``, by event.

        An event nobody listens to is left out.

        Args:
            event_names: The names the steps of a place or a transition go out under.
            transition: The transition they are the steps of; ``None`` for a place.
        """
        described: dict[str, list[dict[str, object]]] = {}
        for event_name in event_names:
            for listener in self._dispatcher.get_listeners(event_name):
                summary = await _summary(await _unwrapped(listener), event_name, transition)
                described.setdefault(event_name, []).append(summary)
        return described


def _event_names(workflow_name: str, steps: Sequence[str], node: str) -> list[str]:
    """Return the names each of ``steps`` goes out under: for every workflow, this one, ``node``."""
    return [
        event_name
        for step in steps
        for event_name in (
            f"workflow.{step}",
            f"workflow.{workflow_name}.{step}",
            f"workflow.{workflow_name}.{step}.{node}",
        )
    ]


async def _unwrapped(listener: Listener | WrappedListener | LazyListener) -> Listener:
    """Return what ``listener`` runs: what a traced listener wraps, what a lazy one builds.

    Building a lazy listener is what dispatching to it would do first; it is
    built once, and runs as what it built from then on.
    """
    if isinstance(listener, WrappedListener):
        return await _unwrapped(listener.get_wrapped_listener())
    if isinstance(listener, LazyListener):
        return await _unwrapped(await listener.resolve())
    return listener


async def _summary(
    listener: Listener, event_name: str, transition: Transition | None
) -> dict[str, object]:
    """Return ``listener`` as a tool shows it: its title, its file, the guards it runs.

    A guard listener run in each unit of work is shown as the guard listener
    it runs, and names the guards in a unit of work it opens for the asking —
    or joins.

    Raises:
        LogicError: If ``listener`` is a guard listener's and there is no
            transition to name the guards of.
    """
    runner = _runner_of(listener)
    title, called = _titled(listener if runner is None else _guard_listener_class().on_transition)
    summary: dict[str, object] = {"title": title, "file": _file_of(called)}
    if runner is not None:
        summary["guardExpressions"] = await runner.get_guard_names(event_name, _guarded(transition))
    elif (guard_listener := _guard_listener_of(listener)) is not None:
        summary["guardExpressions"] = guard_listener.get_guard_names(
            event_name, _guarded(transition)
        )
    return summary


def _guarded(transition: Transition | None) -> Transition:
    """Return the transition whose guards a guard listener is asked to name.

    Raises:
        LogicError: If there is none: the guard listener listens to a place's event.
    """
    if transition is None:
        raise LogicError("Missing event name or transition.")
    return transition


def _titled(listener: Listener) -> tuple[str, Callable[..., object]]:
    """Return the title of ``listener``, and what runs when it is called.

    A method is titled after the class of its object — or its class, for a
    class method — since that is what it is called on; a function, a
    built-in or a class after itself; any other object after its class's
    ``__call__``.
    """
    if inspect.ismethod(listener):
        owner = listener.__self__
        owner_class = owner if isinstance(owner, type) else type(owner)
        return f"{_qualified_name(owner_class)}.{listener.__name__}()", listener
    if inspect.isroutine(listener) or isinstance(listener, type):
        return f"{_qualified_name(listener)}()", listener
    return f"{_qualified_name(type(listener))}.__call__()", listener.__call__


def _qualified_name(target: object) -> str:
    """Return ``target`` as a person looks it up: its module, then its qualified name.

    ``target`` is a class or a routine, which both have a qualified name; a
    built-in method of an object has no module, and is named by its
    qualified name alone.
    """
    module: object = getattr(target, "__module__", None)
    qualified_name: object = getattr(target, "__qualname__", None)
    return f"{module}.{qualified_name}" if isinstance(module, str) else str(qualified_name)


def _file_of(called: Callable[..., object]) -> str | None:
    """Return where the code of ``called`` starts, as ``<path>:<line>``; ``None`` if it has none.

    Only a function written in Python has code to point at. It is reached
    through any decorator that kept what it wraps, so a decorated function
    points at its own code rather than at the decorator's.
    """
    unwrapped = cast("object", inspect.unwrap(called))
    code: object = getattr(unwrapped, "__code__", None)
    if not inspect.iscode(code):
        return None
    return f"{code.co_filename}:{code.co_firstlineno}"


def _guard_listener_of(listener: Listener) -> GuardListener | None:
    """Return the guard listener ``listener`` is a method of; ``None`` when it is none's."""
    guard_listener = _instance_owning(listener, _GUARD_LISTENER_MODULE, "GuardListener")
    return cast("GuardListener | None", guard_listener)


def _runner_of(listener: Listener) -> _GuardListenerOfEachUnitOfWork | None:
    """Return what ``listener`` is a method of, if it runs a guard listener in each unit of work."""
    runner = _instance_owning(
        listener, _UNIT_OF_WORK_GUARD_LISTENER_MODULE, "UnitOfWorkGuardListener"
    )
    return cast("_GuardListenerOfEachUnitOfWork | None", runner)


def _guard_listener_class() -> type[GuardListener]:
    """Return the class of the guard listener built in each unit of work.

    Looked up among the modules imported, as a listener's class is: what runs
    a guard listener in each unit of work is handed this class, so wherever
    one runs, its module has run.
    """
    return cast("type[GuardListener]", sys.modules[_GUARD_LISTENER_MODULE].GuardListener)


def _instance_owning(listener: Listener, module_name: str, class_name: str) -> object | None:
    """Return the object ``listener`` is a method of, if it is a ``class_name`` of ``module_name``.

    The class is looked up among the modules already imported, never imported
    here: the guard listener needs the security core and the bundle's classes
    the container, which an application using neither does not install. An
    object cannot exist before the module of its class has run, so while that
    module is not imported, no listener is a method of one.
    """
    module = sys.modules.get(module_name)
    if module is None or not inspect.ismethod(listener):
        return None
    owner = listener.__self__
    return owner if isinstance(owner, cast("type", getattr(module, class_name))) else None
