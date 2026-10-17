"""A passport carries a user badge, a credential, keyed badges and attributes."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import AuthenticationServiceError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.users import loader
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


def _passport() -> Passport:
    return Passport(UserBadge("alice", user_loader=InMemoryUser), PasswordCredentials("secret"))


def test_it_carries_the_user_badge_and_the_credentials() -> None:
    badge = UserBadge("alice", user_loader=InMemoryUser)
    credentials = PasswordCredentials("secret")
    passport = Passport(badge, credentials)

    assert passport.get_user_badge() is badge
    assert passport.has_badge(UserBadge) is True
    assert passport.get_badge(PasswordCredentials) is credentials


def test_badges_are_keyed_by_class() -> None:
    passport = _passport()
    _ = passport.add_badge(PreAuthenticatedUserBadge())

    assert passport.has_badge(PreAuthenticatedUserBadge) is True
    assert passport.get_badge(PasswordUpgradeBadge) is None
    assert set(passport.get_badges()) == {
        UserBadge,
        PasswordCredentials,
        PreAuthenticatedUserBadge,
    }


def test_a_badge_replaces_one_of_its_class() -> None:
    passport = _passport()
    first = PasswordUpgradeBadge("a")
    second = PasswordUpgradeBadge("b")

    _ = passport.add_badge(first)
    _ = passport.add_badge(second)

    assert passport.get_badge(PasswordUpgradeBadge) is second


def test_a_badge_may_be_keyed_under_another_class() -> None:
    passport = _passport()
    stand_in = PasswordUpgradeBadge("a")

    _ = passport.add_badge(stand_in, PreAuthenticatedUserBadge)

    assert passport.get_badge(PreAuthenticatedUserBadge) is stand_in
    assert passport.has_badge(PasswordUpgradeBadge) is False


def test_attributes_are_a_shared_scratch_space() -> None:
    passport = _passport()

    passport.set_attribute("scope", ["a"])

    assert passport.get_attribute("scope") == ["a"]
    assert passport.get_attribute("missing", "default") == "default"
    assert passport.get_attributes() == {"scope": ["a"]}


async def test_it_loads_the_user_through_the_badge() -> None:
    passport = Passport(
        UserBadge("alice", user_loader=InMemoryUser),
        PasswordCredentials("secret"),
    )

    user = await passport.get_user()

    assert user.get_user_identifier() == "alice"


async def test_it_loads_the_user_once_and_caches_it() -> None:
    passport = Passport(
        UserBadge("alice", user_loader=loader()),
        PasswordCredentials("secret"),
    )

    first = await passport.get_user()
    second = await passport.get_user()

    assert first is second


async def test_loading_without_a_user_badge_is_a_service_error() -> None:
    # A passport built by hand could lack the badge its constructor always
    # adds; asking it for the user is refused rather than crashing.
    passport = _passport()
    passport._badges.clear()

    with pytest.raises(AuthenticationServiceError):
        _ = await passport.get_user()
