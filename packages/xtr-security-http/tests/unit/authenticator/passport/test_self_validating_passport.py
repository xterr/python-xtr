"""A self-validating passport adds a pre-authenticated badge."""

from __future__ import annotations

from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport


def test_it_carries_a_pre_authenticated_badge() -> None:
    passport = SelfValidatingPassport(UserBadge("alice"))

    assert passport.has_badge(PreAuthenticatedUserBadge) is True


def test_a_supplied_pre_authenticated_badge_is_kept() -> None:
    given = PreAuthenticatedUserBadge()
    passport = SelfValidatingPassport(UserBadge("alice"), [given])

    assert passport.get_badge(PreAuthenticatedUserBadge) is given
