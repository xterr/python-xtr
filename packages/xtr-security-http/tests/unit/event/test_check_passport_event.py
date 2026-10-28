"""The check-passport event carries the authenticator and the passport."""

from __future__ import annotations

from xtr_http_kernel.bridge import ResponseFactory

from tests.support.http import FakeAccessTokenHandler
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.event.check_passport_event import CheckPassportEvent


def test_it_carries_the_authenticator_and_passport() -> None:
    passport = SelfValidatingPassport(UserBadge("alice"))
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )

    event = CheckPassportEvent(authenticator, passport)

    assert event.get_authenticator() is authenticator
    assert event.get_passport() is passport
