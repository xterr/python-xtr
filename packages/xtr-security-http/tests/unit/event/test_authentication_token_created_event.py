"""The token-created event exposes and replaces the authenticated token."""

from __future__ import annotations

from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.authentication_token_created_event import (
    AuthenticationTokenCreatedEvent,
)


def test_it_replaces_the_token() -> None:
    passport = Passport(UserBadge("alice"))
    first = NullToken()
    replacement = PostAuthenticationToken(InMemoryUser("alice"), "api", ())

    event = AuthenticationTokenCreatedEvent(first, passport)
    assert event.get_authenticated_token() is first
    assert event.get_passport() is passport

    event.set_authenticated_token(replacement)
    assert event.get_authenticated_token() is replacement
