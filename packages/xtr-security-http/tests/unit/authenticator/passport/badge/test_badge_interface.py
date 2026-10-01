"""The badge interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_http.authenticator.passport.badge.badge_interface import BadgeInterface
from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge


def test_a_badge_satisfies_the_interface() -> None:
    assert isinstance(PreAuthenticatedUserBadge(), BadgeInterface)
    assert isinstance(UserBadge("alice"), BadgeInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), BadgeInterface)
