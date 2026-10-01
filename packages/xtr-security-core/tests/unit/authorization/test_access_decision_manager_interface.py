"""The decision-manager interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.authorization import AccessDecisionManager, AccessDecisionManagerInterface


def test_the_manager_satisfies_the_interface() -> None:
    assert isinstance(AccessDecisionManager(), AccessDecisionManagerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AccessDecisionManagerInterface)
