"""Declaring a listener of the transition event of a workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._build_event_name import build_event_name
from .workflow_listener_declaration import ListenerT, workflow_listener

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from xtr_event_dispatcher.subscribed_listener import OrderTarget

__all__ = ["as_transition_listener"]


def as_transition_listener(  # noqa: PLR0913 — one argument per thing a listener can declare.
    workflow: str | None = None,
    transition: str | None = None,
    *,
    method: str | None = None,
    priority: int | None = None,
    dispatcher: str | None = None,
    before: OrderTarget | Sequence[OrderTarget] | None = None,
    after: OrderTarget | Sequence[OrderTarget] | None = None,
) -> Callable[[ListenerT], ListenerT]:
    """Declare the decorated class, method or function a listener of a workflow's transition event.

    It runs while a transition is applied, once the subject left its places,
    and may replace the call's context with ``set_context``. It declares an
    event listener the way ``@as_event_listener`` does, and takes the same
    keyword arguments.

    Args:
        workflow: The workflow listened to; without it, the workflow the
            listener's class declares with ``@as_workflow``, or every
            workflow outside such a class.
        transition: The transition listened to; every one without it.
        method: On a class, the method to call.
        priority: Higher runs earlier.
        dispatcher: The named dispatcher to listen on.
        before: Listeners this one runs before.
        after: Listeners this one runs after.
    """
    return workflow_listener(
        build_event_name("transition", workflow, transition),
        method=method,
        priority=priority,
        dispatcher=dispatcher,
        before=before,
        after=after,
    )
