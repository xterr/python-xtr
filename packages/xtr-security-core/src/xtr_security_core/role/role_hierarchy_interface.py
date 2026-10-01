"""What expands a set of roles into everything those roles reach."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["RoleHierarchyInterface"]


@runtime_checkable
class RoleHierarchyInterface(Protocol):
    """Turns the roles a token holds into every role they imply.

    A role may stand for others: an administrator's role reaches a user's. A
    voter should not have to know the hierarchy — it asks this to expand the
    token's roles first, then checks the one it wants against the result.
    """

    def get_reachable_role_names(self, roles: Sequence[str]) -> list[str]:
        """Return ``roles`` and every role they reach, transitively.

        The result contains the input roles themselves, then each role reached
        through the hierarchy, with no duplicates and safe against cycles.
        """
        ...
