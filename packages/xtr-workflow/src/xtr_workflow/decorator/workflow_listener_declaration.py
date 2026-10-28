"""What the workflow listener decorators record besides the event listener they declare."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar, cast, final

from xtr_event_dispatcher.decorator import EventListenerDeclaration, as_event_listener
from xtr_event_dispatcher.decorator.event_listener_declaration import recorded_on

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from xtr_event_dispatcher.subscribed_listener import OrderTarget

__all__ = [
    "WORKFLOW_LISTENERS_ATTRIBUTE",
    "ListenerT",
    "WorkflowListenerDeclaration",
    "workflow_listener",
    "workflow_listeners_recorded_on",
]

WORKFLOW_LISTENERS_ATTRIBUTE = "__xtr_workflow_listeners__"
"""Where the workflow listener decorators record their marks."""

ListenerT = TypeVar("ListenerT", bound="Callable[..., object] | type")


@final
@dataclass(frozen=True, slots=True)
class WorkflowListenerDeclaration:
    """Marks an event listener declaration as made by a workflow listener decorator.

    ``workflow.guard`` declared by ``@as_guard_listener()`` and by
    ``@as_event_listener("workflow.guard")`` read the same, but only the first
    belongs to the workflow its class declares: ``@as_workflow`` narrows the
    declarations this marks, and leaves a plain listener of every workflow
    alone.

    Attributes:
        declaration: The event listener declaration the decorator made.
    """

    declaration: EventListenerDeclaration


def workflow_listener(  # noqa: PLR0913 — one argument per thing a listener can declare.
    event: str,
    *,
    method: str | None = None,
    priority: int | None = None,
    dispatcher: str | None = None,
    before: OrderTarget | Sequence[OrderTarget] | None = None,
    after: OrderTarget | Sequence[OrderTarget] | None = None,
) -> Callable[[ListenerT], ListenerT]:
    """Declare a listener of ``event`` with ``@as_event_listener``, and mark the declaration."""
    declare = as_event_listener(
        event, method=method, priority=priority, dispatcher=dispatcher, before=before, after=after
    )

    def decorate(listener: ListenerT) -> ListenerT:
        listener = declare(listener)
        # Where ``@as_event_listener`` recorded: the function a static or
        # class method wraps, or the listener itself.
        target = cast("object", getattr(listener, "__func__", listener))
        mark = WorkflowListenerDeclaration(recorded_on(target)[-1])
        setattr(
            target, WORKFLOW_LISTENERS_ATTRIBUTE, (*workflow_listeners_recorded_on(target), mark)
        )
        return listener

    return decorate


def workflow_listeners_recorded_on(obj: object) -> tuple[WorkflowListenerDeclaration, ...]:
    """Return the marks recorded on ``obj`` itself — a class's own, never its bases'."""
    # Only :func:`workflow_listener` writes the attribute, always as a tuple of marks.
    recorded = (
        vars(obj).get(WORKFLOW_LISTENERS_ATTRIBUTE, ())
        if isinstance(obj, type)
        else getattr(obj, WORKFLOW_LISTENERS_ATTRIBUTE, ())
    )
    return cast("tuple[WorkflowListenerDeclaration, ...]", recorded)
