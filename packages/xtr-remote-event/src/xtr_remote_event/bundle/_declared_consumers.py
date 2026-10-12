"""What a kernel's scan found declared: the class answering for each source name."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_remote_event.exception import LogicError

if TYPE_CHECKING:
    from collections.abc import ItemsView

__all__ = ["DeclaredConsumers"]


@final
class DeclaredConsumers:
    """The consumer classes one kernel found, by the name each answers for.

    One kernel's own, never a registry shared by the process: two kernels in
    one test run declare into one of these each, so a consumer scanned by both
    is a service of both and a clash in one is not a clash in the other.
    """

    __slots__ = ("_by_name", "_classes")

    def __init__(self) -> None:
        """Start with nothing declared."""
        self._by_name: dict[str, type[object]] = {}
        self._classes: set[type[object]] = set()

    def add(self, name: str, consumer: type[object]) -> bool:
        """Record ``consumer`` as the consumer of the source ``name``.

        Returns whether ``consumer`` is new here, so the caller registers it as
        a service once however many names it answers for — one instance serving
        every source it declared, rather than one per name.

        Raises:
            LogicError: If another class already answers for ``name``. Which
                of the two should have it is a choice only the application can
                make, and either answer silently loses the events of the other.
        """
        claimed = self._by_name.get(name)
        if claimed is not None and claimed is not consumer:
            raise LogicError(
                f'The remote event consumer name "{name}" is declared by both '
                f"{claimed.__qualname__} and {consumer.__qualname__}."
            )
        self._by_name[name] = consumer
        is_new = consumer not in self._classes
        self._classes.add(consumer)
        return is_new

    def items(self) -> ItemsView[str, type[object]]:
        """Return each source name with the class that answers for it."""
        return self._by_name.items()
