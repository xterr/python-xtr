"""The abstract authenticator builds a post-authentication token and no-op hooks."""

from __future__ import annotations

import pytest
from starlette.requests import Request
from typing_extensions import override
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.exception import BadCredentialsError

from tests.support.users import loader
from xtr_security_http.authenticator.abstract_authenticator import AbstractAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken

pytestmark = pytest.mark.anyio


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "headers": [], "query_string": b""})


class _Authenticator(AbstractAuthenticator):
    @override
    def supports(self, request: Request) -> bool | None:
        del request
        return True

    @override
    async def authenticate(self, request: Request) -> Passport:
        del request
        return Passport(UserBadge("alice"))


async def _passport_with_loaded_user() -> Passport:
    passport = Passport(UserBadge("root", user_loader=loader(roles=("ROLE_ADMIN",))))
    _ = await passport.get_user()
    return passport


async def test_it_builds_a_post_authentication_token_from_the_loaded_user() -> None:
    passport = await _passport_with_loaded_user()

    token = await _Authenticator().create_token(passport, "api")

    assert isinstance(token, PostAuthenticationToken)
    assert token.get_user_identifier() == "root"
    assert list(token.get_role_names()) == ["ROLE_ADMIN"]
    assert token.get_firewall_name() == "api"


async def test_the_hooks_answer_nothing() -> None:
    authenticator = _Authenticator()

    success = await authenticator.on_authentication_success(_request(), NullToken(), "api")
    failure = await authenticator.on_authentication_failure(_request(), BadCredentialsError())

    assert success is None
    assert failure is None
