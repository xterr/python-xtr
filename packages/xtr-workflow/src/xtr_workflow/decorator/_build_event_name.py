"""The event a workflow listener decorator declares, from the workflow and node it names."""

from __future__ import annotations

from typing import Final

__all__ = ["NAME_PLACEHOLDER", "build_event_name"]

NAME_PLACEHOLDER: Final = "@self"
"""Stands for the workflow of the listener's class until ``@as_workflow`` names it."""


def build_event_name(keyword: str, workflow: str | None = None, node: str | None = None) -> str:
    """Return the event ``keyword`` narrowed to ``workflow`` and to ``node``, a place or transition.

    A node without a workflow is a node of the workflow the listener's class
    declares; ``@as_workflow`` replaces the placeholder with its name. Without
    either, the listener hears the event of every workflow — unless its
    class declares one, which then narrows it too.
    """
    if workflow is None:
        if node is None:
            return f"workflow.{keyword}"
        workflow = NAME_PLACEHOLDER

    if node is None:
        return f"workflow.{workflow}.{keyword}"

    return f"workflow.{workflow}.{keyword}.{node}"
