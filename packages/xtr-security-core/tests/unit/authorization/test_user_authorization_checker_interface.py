"""The user-checker interface is a structural protocol the guest checker extends."""

from __future__ import annotations

from inspect import getmro

from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import (
    AccessDecisionManager,
    AuthorizationChecker,
    GuestAuthorizationCheckerInterface,
    UserAuthorizationCheckerInterface,
)


def test_the_guest_interface_extends_it() -> None:
    assert UserAuthorizationCheckerInterface in getmro(GuestAuthorizationCheckerInterface)


def test_the_checker_satisfies_the_interface() -> None:
    checker = AuthorizationChecker(TokenStorage(), AccessDecisionManager())

    assert isinstance(checker, UserAuthorizationCheckerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), UserAuthorizationCheckerInterface)
