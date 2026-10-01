"""The access-token authenticator reads a token, builds a passport, and challenges."""

from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from typing_extensions import override
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
    InsufficientAuthenticationError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.in_memory_user_provider import InMemoryUserProvider

from tests.support.http import FakeAccessTokenHandler
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authentication.authentication_failure_handler_interface import (
    AuthenticationFailureHandlerInterface,
)
from xtr_security_http.authentication.authentication_success_handler_interface import (
    AuthenticationSuccessHandlerInterface,
)
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.exception import InvalidAccessTokenError

pytestmark = pytest.mark.anyio

_TOKENS = {"good": ("alice", ("books:read", "books:write"))}
_SUCCESS_RESPONSE = JSONResponse({"ok": True})
_FAILURE_RESPONSE = JSONResponse({"ok": False})


class _SuccessHandler(AuthenticationSuccessHandlerInterface):
    @override
    async def on_authentication_success(
        self,
        request: Request,
        token: object,
        firewall_name: str,
    ) -> Response | None:
        del request, token, firewall_name
        return _SUCCESS_RESPONSE


class _FailureHandler(AuthenticationFailureHandlerInterface):
    @override
    async def on_authentication_failure(
        self,
        request: Request,
        error: AuthenticationError,
    ) -> Response | None:
        del request, error
        return _FAILURE_RESPONSE


def _request(authorization: str | None = None) -> Request:
    headers = [(b"authorization", authorization.encode())] if authorization else []
    return Request({"type": "http", "method": "GET", "headers": headers, "query_string": b""})


def _authenticator(realm: str | None = "shop") -> AccessTokenAuthenticator:
    return AccessTokenAuthenticator(
        FakeAccessTokenHandler(_TOKENS),
        HeaderAccessTokenExtractor(),
        user_provider=InMemoryUserProvider(
            {"alice": {"password": None, "roles": [], "enabled": True}}
        ),
        realm=realm,
    )


def test_it_is_always_lazy() -> None:
    assert _authenticator().supports(_request()) is None
    assert _authenticator().supports(_request("Bearer good")) is None


async def test_no_token_is_bad_credentials() -> None:
    with pytest.raises(BadCredentialsError):
        _ = await _authenticator().authenticate(_request())


async def test_a_bad_token_is_invalid_access_token() -> None:
    with pytest.raises(InvalidAccessTokenError):
        _ = await _authenticator().authenticate(_request("Bearer nope"))


async def test_a_good_token_builds_a_self_validating_passport_with_scope() -> None:
    passport = await _authenticator().authenticate(_request("Bearer good"))

    assert isinstance(passport, SelfValidatingPassport)
    assert passport.get_attribute(AccessTokenAuthenticator.SCOPE_ATTRIBUTE) == [
        "books:read",
        "books:write",
    ]


async def test_the_token_copies_the_scope_as_oauth2_scope() -> None:
    authenticator = _authenticator()
    passport = await authenticator.authenticate(_request("Bearer good"))
    _ = await passport.get_user()

    token = await authenticator.create_token(passport, "api")

    assert token.get_attribute("oauth2_scope") == ["books:read", "books:write"]


async def test_a_token_without_scope_carries_no_scope_attribute() -> None:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({"plain": ("alice", ())}),
        HeaderAccessTokenExtractor(),
        user_provider=InMemoryUserProvider(
            {"alice": {"password": None, "roles": [], "enabled": True}},
        ),
    )
    passport = await authenticator.authenticate(_request("Bearer plain"))
    _ = await passport.get_user()

    token = await authenticator.create_token(passport, "api")

    assert token.has_attribute("oauth2_scope") is False


async def test_start_without_error_is_a_bare_challenge() -> None:
    response = await _authenticator().start(_request())

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Bearer realm="shop"'


async def test_start_with_an_invalid_token_names_the_error() -> None:
    response = await _authenticator().start(_request(), InvalidAccessTokenError())

    challenge = response.headers["www-authenticate"]
    assert 'error="invalid_token"' in challenge
    assert "error_description=" in challenge


async def test_start_with_insufficient_authentication_stays_bare() -> None:
    response = await _authenticator().start(_request(), InsufficientAuthenticationError())

    assert response.headers["www-authenticate"] == 'Bearer realm="shop"'


async def test_start_without_a_realm_omits_it() -> None:
    response = await _authenticator(realm=None).start(_request())

    assert response.headers["www-authenticate"] == "Bearer"


async def test_a_scope_string_is_split() -> None:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
    )
    badge = UserBadge("alice", user_loader=InMemoryUser)
    passport = SelfValidatingPassport(badge)
    _ = await passport.get_user()
    passport.set_attribute(AccessTokenAuthenticator.SCOPE_ATTRIBUTE, "a b")

    token = await authenticator.create_token(passport, "api")

    assert token.get_attribute("oauth2_scope") == ["a", "b"]


async def test_the_handlers_are_delegated_to() -> None:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        success_handler=_SuccessHandler(),
        failure_handler=_FailureHandler(),
    )

    success = await authenticator.on_authentication_success(_request(), NullToken(), "api")
    failure = await authenticator.on_authentication_failure(_request(), BadCredentialsError())

    assert success is _SUCCESS_RESPONSE
    assert failure is _FAILURE_RESPONSE
