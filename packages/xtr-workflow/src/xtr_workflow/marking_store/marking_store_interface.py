"""Where a workflow reads a subject's marking, and writes it back."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow.marking import Marking

__all__ = ["MarkingStoreInterface"]


@runtime_checkable
class MarkingStoreInterface(Protocol):
    """Reads the marking a subject is in, and records the one a transition moved it to.

    It translates between a workflow's :class:`~xtr_workflow.marking.Marking`
    and whatever keeps it — the subject's own attribute, or something else
    entirely: a session, a cache, a remote service. That is why both methods
    are coroutines: a store may have to wait on what keeps the marking.
    """

    async def get_marking(self, subject: object) -> Marking:
        """Return the marking ``subject`` is in; empty when it was never given one."""
        ...

    async def set_marking(
        self,
        subject: object,
        marking: Marking,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Record ``marking`` as the one ``subject`` is in now.

        Args:
            subject: The object the workflow moved.
            marking: Where it is now.
            context: The context the transition that moved it ran with, for a
                store that keeps it too.
        """
        ...
