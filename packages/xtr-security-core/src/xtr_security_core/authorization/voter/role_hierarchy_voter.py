"""A role voter that expands the token's roles through a hierarchy first."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from .role_voter import RoleVoter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.role.role_hierarchy_interface import RoleHierarchyInterface

__all__ = ["RoleHierarchyVoter"]


class RoleHierarchyVoter(RoleVoter):
    """Uses a role hierarchy to determine the roles granted to the user before voting.

    The same as :class:`~xtr_security_core.authorization.voter.role_voter.RoleVoter`,
    except the token's roles are first expanded through the hierarchy — so a
    token holding ``ROLE_ADMIN`` is granted ``ROLE_USER`` when the hierarchy
    says the one reaches the other.
    """

    __slots__: tuple[str, ...] = ("_role_hierarchy",)

    _role_hierarchy: RoleHierarchyInterface

    def __init__(self, role_hierarchy: RoleHierarchyInterface, prefix: str = "ROLE_") -> None:
        """Record the hierarchy to expand the token's roles through."""
        super().__init__(prefix)
        self._role_hierarchy = role_hierarchy

    @override
    def _extract_roles(self, token: TokenInterface) -> Sequence[str]:
        """Return the token's roles and every role they reach through the hierarchy."""
        return self._role_hierarchy.get_reachable_role_names(token.get_role_names())
