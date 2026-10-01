"""The guest-checker interface is a structural protocol."""

from __future__ import annotations

from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import (
    AccessDecisionManager,
    AuthorizationChecker,
    GuestAuthorizationCheckerInterface,
)


def test_the_checker_satisfies_the_interface() -> None:
    checker = AuthorizationChecker(TokenStorage(), AccessDecisionManager())

    assert isinstance(checker, GuestAuthorizationCheckerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), GuestAuthorizationCheckerInterface)
