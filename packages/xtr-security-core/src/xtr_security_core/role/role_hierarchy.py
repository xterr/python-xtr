"""A role hierarchy, with wildcard placeholders."""

from __future__ import annotations

import re
from collections import deque
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_security_core.exception import InvalidArgumentError

from .role_hierarchy_interface import RoleHierarchyInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["RoleHierarchy"]

#: A cap on how many roles one expansion may reach. A finite hierarchy never
#: comes close; a wildcard entry that feeds its own output could otherwise grow
#: without bound, so expansion stops here rather than loop forever.
_MAX_REACHABLE: Final = 10_000

#: A cap on how many distinct role sets keep a memoised expansion. Real
#: applications ask about a small, fixed set of role combinations; the cap keeps
#: a pathological caller from growing the memo without bound.
_MAX_MEMO: Final = 1024


@final
class RoleHierarchy(RoleHierarchyInterface):
    """Expands roles through a declared hierarchy, cycles and wildcards included.

    The hierarchy maps a role to the roles it reaches directly:
    ``{"ROLE_ADMIN": ["ROLE_USER"]}`` makes ``ROLE_ADMIN`` reach ``ROLE_USER``.
    Reaching is transitive — a role reaches what its children reach — and safe
    against cycles: each role is expanded once.

    A ``*`` in a key is a placeholder that captures a segment of a matching
    role and substitutes it into the values:
    ``{"ROLE_TENANT_*_ADMIN": ["ROLE_TENANT_*_USER"]}`` makes
    ``ROLE_TENANT_42_ADMIN`` reach ``ROLE_TENANT_42_USER``. Several ``*`` in
    one key are captured left to right and substituted into the values in the
    same order.
    """

    __slots__ = ("_exact", "_memo", "_wildcards")

    def __init__(self, hierarchy: Mapping[str, Sequence[str]] | None = None) -> None:
        """Split the declared hierarchy into exact keys and wildcard patterns.

        Raises:
            InvalidArgumentError: When a wildcard key's value asks for more
                ``*`` placeholders than the key can capture, which would
                substitute the empty string for the surplus.
        """
        self._exact: dict[str, tuple[str, ...]] = {}
        self._wildcards: list[tuple[re.Pattern[str], tuple[str, ...]]] = []
        self._memo: dict[frozenset[str], tuple[str, ...]] = {}
        for key, values in (hierarchy or {}).items():
            parents = tuple(values)
            if "*" in key:
                captures = key.count("*")
                for parent in parents:
                    if parent.count("*") > captures:
                        raise InvalidArgumentError(
                            f'Role "{parent}" asks for more wildcards than "{key}" captures.',
                        )
                parts = key.split("*")
                pattern = re.compile("^" + "(.+?)".join(re.escape(part) for part in parts) + "$")
                self._wildcards.append((pattern, parents))
            else:
                self._exact[key] = parents

    @override
    def get_reachable_role_names(self, roles: Sequence[str]) -> list[str]:
        """Return ``roles`` and every role they reach, transitively.

        The expansion of a given set of roles is memoised, so a voter asking the
        same question every decision runs the search once.
        """
        key = frozenset(roles)
        cached = self._memo.get(key)
        if cached is not None:
            return list(cached)
        reachable: list[str] = []
        seen: set[str] = set()
        pending: deque[str] = deque(roles)
        while pending and len(reachable) < _MAX_REACHABLE:
            role = pending.popleft()
            if role in seen:
                continue
            seen.add(role)
            reachable.append(role)
            pending.extend(parent for parent in self._parents_of(role) if parent not in seen)
        if len(self._memo) >= _MAX_MEMO:
            _ = self._memo.pop(next(iter(self._memo)))
        self._memo[key] = tuple(reachable)
        return reachable

    def get_parent_role_names(self, role: str) -> list[str]:
        """Return the roles ``role`` reaches directly, one level down."""
        return self._parents_of(role)

    def _parents_of(self, role: str) -> list[str]:
        """Return the direct parents of ``role``, wildcard patterns expanded."""
        parents: list[str] = list(self._exact.get(role, ()))
        for pattern, values in self._wildcards:
            match = pattern.fullmatch(role)
            if match is not None:
                captures = match.groups()
                parents.extend(_substitute(value, captures) for value in values)
        return parents


def _substitute(template: str, captures: tuple[str, ...]) -> str:
    """Replace each ``*`` in ``template`` with the next captured segment."""
    parts = template.split("*")
    result = parts[0]
    for index, part in enumerate(parts[1:]):
        result += (captures[index] if index < len(captures) else "") + part
    return result
