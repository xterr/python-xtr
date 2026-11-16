"""A marking store that writes a marking only over the one it was read as."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .marking_store_interface import MarkingStoreInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow.marking import Marking

__all__ = ["CompareAndSetMarkingStoreInterface"]


@runtime_checkable
class CompareAndSetMarkingStoreInterface(MarkingStoreInterface, Protocol):
    """Writes a subject's new marking only while the stored one is still the expected one.

    A workflow keeps two transitions of one subject object apart within the
    process; two processes — or two requests each loading the subject into
    an object of its own — are kept apart only by the store. A store that
    implements this, through a conditional ``UPDATE`` or a version column, is
    the one a workflow writes through, and it refuses a transition whose
    subject moved meanwhile.
    """

    async def set_marking_if(
        self,
        subject: object,
        marking: Marking,
        expected: Marking,
        context: Mapping[str, object] | None = None,
    ) -> bool:
        """Record ``marking`` as ``subject``'s, if it is still in ``expected``.

        Args:
            subject: The object the workflow moved.
            marking: Where it is now.
            expected: Where it was when the transition was weighed.
            context: The context the transition that moved it ran with.

        Returns:
            ``True`` when the marking was written; ``False`` when the stored
            one was no longer ``expected``, so nothing was.
        """
        ...
