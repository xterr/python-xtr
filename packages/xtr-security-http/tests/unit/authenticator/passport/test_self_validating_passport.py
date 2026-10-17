"""A self-validating passport carries no credentials and no auto-added badge."""

from __future__ import annotations

from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport


def test_it_carries_the_user_badge_and_no_credentials() -> None:
    badge = UserBadge("alice")
    passport = SelfValidatingPassport(badge)

    assert passport.get_user_badge() is badge
    assert passport.has_badge(PasswordCredentials) is False


def test_it_adds_no_pre_authenticated_badge_of_its_own() -> None:
    passport = SelfValidatingPassport(UserBadge("alice"))

    assert passport.has_badge(PreAuthenticatedUserBadge) is False


def test_a_supplied_pre_authenticated_badge_is_kept() -> None:
    given = PreAuthenticatedUserBadge()
    passport = SelfValidatingPassport(UserBadge("alice"), [given])

    assert passport.get_badge(PreAuthenticatedUserBadge) is given
