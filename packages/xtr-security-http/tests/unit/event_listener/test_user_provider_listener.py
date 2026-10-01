"""The user-provider listener sets the badge's user loader from the provider."""

from __future__ import annotations

import pytest
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.in_memory_user_provider import InMemoryUserProvider

from tests.support.http import FakeAccessTokenHandler
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event_listener.user_provider_listener import UserProviderListener

pytestmark = pytest.mark.anyio


def _event(passport: Passport) -> CheckPassportEvent:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}), HeaderAccessTokenExtractor()
    )
    return CheckPassportEvent(authenticator, passport)


async def test_it_sets_the_loader() -> None:
    provider = InMemoryUserProvider({"alice": {"password": None, "roles": [], "enabled": True}})
    passport = Passport(UserBadge("alice"))

    await UserProviderListener(provider).check_passport(_event(passport))

    assert passport.get_user_badge().is_resolved() is True
    user = await passport.get_user()
    assert user.get_user_identifier() == "alice"


async def test_it_leaves_an_existing_loader() -> None:
    provider = InMemoryUserProvider({})
    loader = InMemoryUser
    passport = Passport(UserBadge("alice", user_loader=loader))

    await UserProviderListener(provider).check_passport(_event(passport))

    assert passport.get_user_badge().get_user_loader() is loader
