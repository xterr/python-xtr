"""The authorization-checker interface is a structural protocol."""

from __future__ import annotations

from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import (
    AccessDecisionManager,
    AuthorizationChecker,
    AuthorizationCheckerInterface,
)


def _checker() -> AuthorizationChecker:
    return AuthorizationChecker(TokenStorage(), AccessDecisionManager())


def test_the_checker_satisfies_the_interface() -> None:
    assert isinstance(_checker(), AuthorizationCheckerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AuthorizationCheckerInterface)
