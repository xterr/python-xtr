"""Writes a definition out as the source of a diagram."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow.definition import Definition
    from xtr_workflow.marking import Marking

__all__ = ["DumperInterface"]


@runtime_checkable
class DumperInterface(Protocol):
    """Writes a definition out as the source of a diagram a drawing tool renders.

    Each dumper speaks one diagram language; the options it reads are its
    own, and it ignores those it does not know, so one set of options can be
    handed to whichever dumper was picked.
    """

    def dump(
        self,
        definition: Definition,
        marking: Marking | None = None,
        options: Mapping[str, object] | None = None,
    ) -> str:
        """Return the diagram source of ``definition``.

        Args:
            definition: The places and transitions to draw.
            marking: Where a subject is, highlighted on the diagram; nothing
                is highlighted when ``None``.
            options: What the dumper reads to style the diagram.
        """
        ...
