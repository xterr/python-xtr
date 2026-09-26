"""A pool that can hand out a view of itself confined to a sub-namespace."""

from __future__ import annotations

from typing import Protocol, Self, runtime_checkable

__all__ = ["NamespacedPoolInterface"]


@runtime_checkable
class NamespacedPoolInterface(Protocol):
    """Confines keys to a sub-namespace, so a group of them can be dropped at once.

    Keys written through the returned pool are prefixed with the backend's
    own namespace separator, so clearing that namespace invalidates them
    together without listing them. Tags ignore sub-namespaces: invalidating a
    tag reaches a value whichever sub-namespace it was saved in.
    """

    def with_sub_namespace(self, namespace: str, /) -> Self:
        """Return a pool whose keys live under ``namespace``, inside this pool's namespace.

        This pool is left as it was; the returned one is new.

        Raises:
            InvalidArgumentError: When ``namespace`` is empty or holds a
                reserved character.
        """
        ...
