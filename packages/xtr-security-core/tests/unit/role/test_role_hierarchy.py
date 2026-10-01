"""The role hierarchy expands roles, with wildcards, and survives cycles."""

from __future__ import annotations

import pytest

from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.role import RoleHierarchy, RoleHierarchyInterface
from xtr_security_core.role.role_hierarchy import _MAX_REACHABLE


def test_it_inherits_the_role_hierarchy_interface() -> None:
    assert RoleHierarchyInterface in RoleHierarchy.__mro__


def test_no_hierarchy_reaches_only_the_given_roles() -> None:
    hierarchy = RoleHierarchy()

    assert hierarchy.get_reachable_role_names(["ROLE_USER"]) == ["ROLE_USER"]


def test_direct_reach() -> None:
    hierarchy = RoleHierarchy({"ROLE_ADMIN": ["ROLE_USER"]})

    reachable = hierarchy.get_reachable_role_names(["ROLE_ADMIN"])

    assert reachable == ["ROLE_ADMIN", "ROLE_USER"]


def test_transitive_reach() -> None:
    hierarchy = RoleHierarchy(
        {"ROLE_SUPER": ["ROLE_ADMIN"], "ROLE_ADMIN": ["ROLE_USER"]},
    )

    reachable = hierarchy.get_reachable_role_names(["ROLE_SUPER"])

    assert set(reachable) == {"ROLE_SUPER", "ROLE_ADMIN", "ROLE_USER"}


def test_no_duplicates() -> None:
    hierarchy = RoleHierarchy(
        {"ROLE_A": ["ROLE_C"], "ROLE_B": ["ROLE_C"]},
    )

    reachable = hierarchy.get_reachable_role_names(["ROLE_A", "ROLE_B"])

    assert reachable.count("ROLE_C") == 1


def test_a_direct_cycle_is_safe() -> None:
    hierarchy = RoleHierarchy({"ROLE_A": ["ROLE_B"], "ROLE_B": ["ROLE_A"]})

    reachable = hierarchy.get_reachable_role_names(["ROLE_A"])

    assert set(reachable) == {"ROLE_A", "ROLE_B"}


def test_a_self_cycle_is_safe() -> None:
    hierarchy = RoleHierarchy({"ROLE_A": ["ROLE_A"]})

    assert hierarchy.get_reachable_role_names(["ROLE_A"]) == ["ROLE_A"]


def test_wildcard_captures_and_substitutes_a_segment() -> None:
    hierarchy = RoleHierarchy({"ROLE_TENANT_*_ADMIN": ["ROLE_TENANT_*_USER"]})

    reachable = hierarchy.get_reachable_role_names(["ROLE_TENANT_42_ADMIN"])

    assert reachable == ["ROLE_TENANT_42_ADMIN", "ROLE_TENANT_42_USER"]


def test_wildcard_does_not_match_a_different_shape() -> None:
    hierarchy = RoleHierarchy({"ROLE_TENANT_*_ADMIN": ["ROLE_TENANT_*_USER"]})

    assert hierarchy.get_reachable_role_names(["ROLE_OTHER"]) == ["ROLE_OTHER"]


def test_wildcard_to_a_fixed_role() -> None:
    hierarchy = RoleHierarchy({"ROLE_TENANT_*": ["ROLE_MEMBER"]})

    reachable = hierarchy.get_reachable_role_names(["ROLE_TENANT_7"])

    assert set(reachable) == {"ROLE_TENANT_7", "ROLE_MEMBER"}


def test_get_parent_role_names_is_one_level() -> None:
    hierarchy = RoleHierarchy(
        {"ROLE_SUPER": ["ROLE_ADMIN"], "ROLE_ADMIN": ["ROLE_USER"]},
    )

    assert hierarchy.get_parent_role_names("ROLE_SUPER") == ["ROLE_ADMIN"]


def test_multiple_wildcards_substitute_in_order() -> None:
    hierarchy = RoleHierarchy({"ROLE_*_*_ADMIN": ["ROLE_*_*_USER"]})

    reachable = hierarchy.get_reachable_role_names(["ROLE_EU_42_ADMIN"])

    assert reachable == ["ROLE_EU_42_ADMIN", "ROLE_EU_42_USER"]


def test_a_self_feeding_wildcard_stops_at_the_cap() -> None:
    hierarchy = RoleHierarchy({"ROLE_*": ["ROLE_X_*"]})

    reachable = hierarchy.get_reachable_role_names(["ROLE_A"])

    assert len(reachable) == _MAX_REACHABLE


def test_a_value_with_more_wildcards_than_its_key_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = RoleHierarchy({"ROLE_*_A": ["ROLE_*_*_B"]})


def test_the_expansion_of_a_role_set_is_memoised() -> None:
    hierarchy = RoleHierarchy({"ROLE_ADMIN": ["ROLE_USER"]})

    first = hierarchy.get_reachable_role_names(["ROLE_ADMIN"])
    second = hierarchy.get_reachable_role_names(["ROLE_ADMIN"])

    assert first == second
    assert first is not second
