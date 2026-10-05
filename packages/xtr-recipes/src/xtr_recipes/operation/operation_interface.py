"""What one step of a plan looks like, whether or not it touches the project."""

from __future__ import annotations

from typing import ClassVar, Protocol, runtime_checkable

__all__ = ["OperationInterface"]


@runtime_checkable
class OperationInterface(Protocol):
    """One step of a plan: what it would say, and what it would do.

    A plan is computed in full before anything is written, so a command can
    print it and stop — that is the whole of ``--dry-run`` and ``--check``.
    Every step therefore answers twice: :meth:`render` for the person reading,
    :meth:`apply` for the project on disk.

    Attributes:
        changes: Whether applying this step changes the project. A step that
            only reports — a section heading, a file left alone, a bundle
            another one already requires — says ``False``, which is what lets
            ``--check`` pass on a plan made entirely of messages.
    """

    changes: ClassVar[bool]

    def render(self) -> tuple[str, ...]:
        """Return the lines reporting this step, already indented."""
        ...

    def apply(self) -> None:
        """Carry the step out; a reporting step does nothing."""
        ...
