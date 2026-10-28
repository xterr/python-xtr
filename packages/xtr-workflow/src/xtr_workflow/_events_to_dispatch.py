"""Reading which events a workflow is told to dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from .exception import InvalidArgumentError
from .workflow_events import WorkflowEvents

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["events_to_dispatch_from"]

# Every event but the guard, which is never suppressed, in the order a transition dispatches them.
_DISPATCHABLE_EVENTS: Final[tuple[str, ...]] = (
    WorkflowEvents.LEAVE,
    WorkflowEvents.TRANSITION,
    WorkflowEvents.ENTER,
    WorkflowEvents.ENTERED,
    WorkflowEvents.COMPLETED,
    WorkflowEvents.ANNOUNCE,
)


def events_to_dispatch_from(events_to_dispatch: Sequence[str], name: str) -> frozenset[str]:
    """Return the events ``events_to_dispatch`` lets out, a block-list read as what it leaves.

    A block-list is turned into the events it leaves once, here, so that
    deciding whether an event goes out is one lookup however it was given.

    Args:
        events_to_dispatch: The events listed, or — every entry starting with
            ``!`` — the events kept back.
        name: The name of the workflow, for the error messages.

    Raises:
        InvalidArgumentError: If it mixes listed and ``!``-prefixed entries, or
            blocks the guard.
    """
    blocked = [entry.removeprefix("!") for entry in events_to_dispatch if entry.startswith("!")]
    if not blocked:
        return frozenset(events_to_dispatch)

    if len(blocked) != len(events_to_dispatch):
        raise InvalidArgumentError(
            "Cannot mix allow-list and block-list entries in events_to_dispatch for workflow "
            f'"{name}": every entry must start with "!" (block-list mode) or none of them must '
            "(allow-list mode)."
        )
    if WorkflowEvents.GUARD in blocked:
        raise InvalidArgumentError(
            f'The "{WorkflowEvents.GUARD}" event cannot be disabled in events_to_dispatch for '
            f'workflow "{name}": it is always dispatched.'
        )

    return frozenset(event for event in _DISPATCHABLE_EVENTS if event not in blocked)
