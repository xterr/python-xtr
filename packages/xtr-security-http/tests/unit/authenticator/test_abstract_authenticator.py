"""The abstract authenticator builds a post-authentication token and no-op hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.exception import BadCredentialsError

from tests.support.messages import make_message
from tests.support.users import loader
from xtr_security_http.authenticator.abstract_authenticator import AbstractAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http.authenticator.passport.passport import Passport

pytestmark = pytest.mark.anyio


class _Authenticator(AbstractAuthenticator):
    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        return True

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        del request
        return SelfValidatingPassport(UserBadge("alice"))


async def _passport_with_loaded_user() -> Passport:
    passport = SelfValidatingPassport(UserBadge("root", user_loader=loader(roles=("ROLE_ADMIN",))))
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

    success: ResponseInterface | None = await authenticator.on_authentication_success(
        make_message(), NullToken(), "api"
    )
    failure: ResponseInterface | None = await authenticator.on_authentication_failure(
        make_message(), BadCredentialsError()
    )

    assert success is None
    assert failure is None
