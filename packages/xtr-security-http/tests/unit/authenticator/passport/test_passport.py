"""A passport carries a user badge, keyed badges, and shared attributes."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import BadCredentialsError
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.authenticator.passport.passport import Passport

pytestmark = pytest.mark.anyio


def test_it_carries_the_user_badge() -> None:
    badge = UserBadge("alice")
    passport = Passport(badge)

    assert passport.get_user_badge() is badge
    assert passport.has_badge(UserBadge) is True


def test_badges_are_keyed_by_class() -> None:
    passport = Passport(UserBadge("alice"), [PreAuthenticatedUserBadge()])

    assert passport.has_badge(PreAuthenticatedUserBadge) is True
    assert passport.get_badge(PasswordUpgradeBadge) is None
    assert set(passport.get_badges()) == {UserBadge, PreAuthenticatedUserBadge}


def test_a_badge_replaces_one_of_its_class() -> None:
    passport = Passport(UserBadge("alice"))
    first = PasswordUpgradeBadge("a")
    second = PasswordUpgradeBadge("b")

    _ = passport.add_badge(first)
    _ = passport.add_badge(second)

    assert passport.get_badge(PasswordUpgradeBadge) is second


def test_attributes_are_a_shared_scratch_space() -> None:
    passport = Passport(UserBadge("alice"))

    passport.set_attribute("scope", ["a"])

    assert passport.get_attribute("scope") == ["a"]
    assert passport.get_attribute("missing", "default") == "default"
    assert passport.get_attributes() == {"scope": ["a"]}


async def test_it_loads_the_user_through_the_badge() -> None:
    passport = Passport(UserBadge("alice", user_loader=InMemoryUser))

    user = await passport.get_user()

    assert user.get_user_identifier() == "alice"


def test_an_unresolved_badge_fails_the_completeness_check() -> None:
    passport = Passport(UserBadge("alice", user_loader=InMemoryUser))
    _ = passport.add_badge(PasswordCredentials("secret"))

    with pytest.raises(BadCredentialsError):
        passport.check_if_completely_resolved()


def test_all_resolved_badges_pass_the_completeness_check() -> None:
    passport = Passport(UserBadge("alice", user_loader=InMemoryUser))

    passport.check_if_completely_resolved()
