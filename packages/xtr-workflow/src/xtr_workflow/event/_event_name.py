"""The names a workflow event is dispatched under."""

from __future__ import annotations

from xtr_workflow.exception import InvalidArgumentError

__all__ = ["event_name"]


def event_name(event_type: type, workflow_name: str | None, node: str | None) -> str:
    """Return the name ``event_type`` is dispatched under, narrowed as far as asked.

    Each event goes out under three names, from the widest to the narrowest:
    ``workflow.<event>`` for every workflow, ``workflow.<name>.<event>`` for
    one, and ``workflow.<name>.<event>.<node>`` for one of its places or
    transitions — so a listener hears exactly what it cares about. ``<event>``
    is the class's name, lower-cased, without its ``Event`` suffix.

    Raises:
        InvalidArgumentError: If ``node`` is given without ``workflow_name``:
            a place or transition name means nothing outside its workflow.
    """
    short_name = event_type.__name__.removesuffix("Event").lower()
    if workflow_name is None:
        if node is not None:
            raise InvalidArgumentError("Missing workflow name.")
        return f"workflow.{short_name}"

    if node is None:
        return f"workflow.{workflow_name}.{short_name}"

    return f"workflow.{workflow_name}.{short_name}.{node}"
