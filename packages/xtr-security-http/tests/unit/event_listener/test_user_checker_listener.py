"""The user-checker listener runs the pre- and post-authentication checks."""

from __future__ import annotations

import pytest
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.exception import DisabledError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.in_memory_user_checker import InMemoryUserChecker

from tests.support.http import FakeAccessTokenHandler
from tests.support.users import loader
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event_listener.user_checker_listener import UserCheckerListener

pytestmark = pytest.mark.anyio


def _event(passport: Passport) -> CheckPassportEvent:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}), HeaderAccessTokenExtractor()
    )
    return CheckPassportEvent(authenticator, passport)


async def test_it_runs_pre_and_post_checks() -> None:
    listener = UserCheckerListener(InMemoryUserChecker())
    good = Passport(UserBadge("alice", user_loader=InMemoryUser))

    await listener.pre_check_credentials(_event(good))

    token = PostAuthenticationToken(InMemoryUser("alice"), "api", ())
    await listener.post_check_credentials(AuthenticationSuccessEvent(token))


async def test_it_rejects_a_disabled_account() -> None:
    listener = UserCheckerListener(InMemoryUserChecker())
    disabled = Passport(UserBadge("alice", user_loader=loader(enabled=False)))

    with pytest.raises(DisabledError):
        await listener.pre_check_credentials(_event(disabled))
