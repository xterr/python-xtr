"""The role-hierarchy interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.role import RoleHierarchy, RoleHierarchyInterface


def test_the_hierarchy_satisfies_the_interface() -> None:
    assert isinstance(RoleHierarchy(), RoleHierarchyInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), RoleHierarchyInterface)
