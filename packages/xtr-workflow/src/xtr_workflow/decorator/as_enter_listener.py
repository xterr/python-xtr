"""Declaring a listener of the enter event of a workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._build_event_name import build_event_name
from .workflow_listener_declaration import ListenerT, workflow_listener

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from xtr_event_dispatcher.subscribed_listener import OrderTarget

__all__ = ["as_enter_listener"]


def as_enter_listener(  # noqa: PLR0913 — one argument per thing a listener can declare.
    workflow: str | None = None,
    place: str | None = None,
    *,
    method: str | None = None,
    priority: int | None = None,
    dispatcher: str | None = None,
    before: OrderTarget | Sequence[OrderTarget] | None = None,
    after: OrderTarget | Sequence[OrderTarget] | None = None,
) -> Callable[[ListenerT], ListenerT]:
    """Declare the decorated class, method or function a listener of a workflow's enter event.

    It runs as a transition puts the subject in a place, before the marking
    is stored. It declares an event listener the way ``@as_event_listener``
    does, and takes the same keyword arguments.

    Args:
        workflow: The workflow listened to; without it, the workflow the
            listener's class declares with ``@as_workflow``, or every
            workflow outside such a class.
        place: The place entered; every one without it.
        method: On a class, the method to call.
        priority: Higher runs earlier.
        dispatcher: The named dispatcher to listen on.
        before: Listeners this one runs before.
        after: Listeners this one runs after.
    """
    return workflow_listener(
        build_event_name("enter", workflow, place),
        method=method,
        priority=priority,
        dispatcher=dispatcher,
        before=before,
        after=after,
    )
