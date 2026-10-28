"""The access-token authenticator reads a token, builds a passport, and challenges."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
    InsufficientAuthenticationError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.in_memory_user_provider import InMemoryUserProvider

from tests.support.http import FakeAccessTokenHandler, FakeSenderConstraint
from tests.support.messages import make_message
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authentication.authentication_failure_handler_interface import (
    AuthenticationFailureHandlerInterface,
)
from xtr_security_http.authentication.authentication_success_handler_interface import (
    AuthenticationSuccessHandlerInterface,
)
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.fallback_user_loader import FallbackUserLoader
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.entry_point.fallback_authentication_entry_point_interface import (
    FallbackAuthenticationEntryPointInterface,
)
from xtr_security_http.exception import InvalidAccessTokenError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

pytestmark = pytest.mark.anyio

_TOKENS = {"good": ("alice", ("books:read", "books:write"))}
_SUCCESS_RESPONSE = ResponseFactory().create_response(200)
_FAILURE_RESPONSE = ResponseFactory().create_response(401)


class _SuccessHandler(AuthenticationSuccessHandlerInterface):
    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface | None:
        del request, token
        return _SUCCESS_RESPONSE


class _FailureHandler(AuthenticationFailureHandlerInterface):
    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        del request, error
        return _FAILURE_RESPONSE


class _AttributesHandler(AccessTokenHandlerInterface):
    """A handler whose badge carries exactly the attributes it was built with."""

    def __init__(self, attributes: Mapping[str, object]) -> None:
        self._attributes: dict[str, object] = dict(attributes)

    @override
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        del access_token
        return UserBadge("alice", attributes=self._attributes)


class _MarkedLoaderHandler(AccessTokenHandlerInterface):
    """A handler whose badge carries a stand-in loader the provider replaces."""

    @override
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        del access_token
        return UserBadge("alice", user_loader=FallbackUserLoader())


def _request(authorization: str | None = None) -> ServerRequestInterface:
    headers = {"authorization": authorization} if authorization else None
    return make_message(headers=headers)


def _authenticator(realm: str | None = "shop") -> AccessTokenAuthenticator:
    return AccessTokenAuthenticator(
        FakeAccessTokenHandler(_TOKENS),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
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
        ResponseFactory(),
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

    assert response.get_status_code() == 401
    assert response.get_header_line("www-authenticate") == 'Bearer realm="shop"'


async def test_start_never_names_an_error() -> None:
    """RFC 6750 Section 3: a request that carried no token is told no error code.

    An error code describes a token the client did send; naming one here
    would describe a token this challenge never saw. A rejected token is
    the failure hook's to answer, with ``invalid_token``.
    """
    response = await _authenticator().start(_request(), InvalidAccessTokenError())

    assert response.get_header_line("www-authenticate") == 'Bearer realm="shop"'


async def test_start_with_insufficient_authentication_stays_bare() -> None:
    response = await _authenticator().start(_request(), InsufficientAuthenticationError())

    assert response.get_header_line("www-authenticate") == 'Bearer realm="shop"'


async def test_start_without_a_realm_omits_it() -> None:
    response = await _authenticator(realm=None).start(_request())

    assert response.get_header_line("www-authenticate") == "Bearer"


async def test_the_challenge_is_not_cached() -> None:
    response = await _authenticator().start(_request())

    assert response.get_header_line("cache-control") == "no-store"
    assert response.get_header_line("pragma") == "no-cache"


async def test_a_scope_string_is_split() -> None:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
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
        ResponseFactory(),
        success_handler=_SuccessHandler(),
        failure_handler=_FailureHandler(),
    )

    success = await authenticator.on_authentication_success(_request(), NullToken(), "api")
    failure = await authenticator.on_authentication_failure(_request(), BadCredentialsError())

    assert success is _SUCCESS_RESPONSE
    assert failure is _FAILURE_RESPONSE


def test_the_extractor_is_exposed() -> None:
    extractor = HeaderAccessTokenExtractor()
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        extractor,
        ResponseFactory(),
    )

    assert authenticator.extractor is extractor


def test_the_authenticator_only_stands_in_as_an_entry_point() -> None:
    assert isinstance(_authenticator(), FallbackAuthenticationEntryPointInterface)


async def test_the_sender_constraint_weighs_the_request_against_the_token() -> None:
    constraint = FakeSenderConstraint()
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler(_TOKENS),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
        sender_constraint=constraint,
    )
    request = _request("Bearer good")

    _ = await authenticator.authenticate(request)

    assert constraint.checked is not None
    weighed_request, presented, claims = constraint.checked
    assert weighed_request is request
    assert presented == "good"
    assert claims == {"scope": ["books:read", "books:write"]}


async def test_a_request_the_constraint_refuses_fails_the_authentication() -> None:
    constraint = FakeSenderConstraint(refusal=BadCredentialsError("The proof does not check out."))
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler(_TOKENS),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
        sender_constraint=constraint,
    )

    with pytest.raises(BadCredentialsError, match=re.escape("The proof does not check out.")):
        _ = await authenticator.authenticate(_request("Bearer good"))


async def test_a_marked_loader_is_replaced_by_the_provider() -> None:
    authenticator = AccessTokenAuthenticator(
        _MarkedLoaderHandler(),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
        user_provider=InMemoryUserProvider(
            {"alice": {"password": None, "roles": [], "enabled": True}}
        ),
    )

    passport = await authenticator.authenticate(_request("Bearer good"))
    user = await passport.get_user()

    assert user.get_user_identifier() == "alice"


async def test_the_badges_own_loader_is_kept() -> None:
    def load(identifier: str) -> InMemoryUser:
        return InMemoryUser(identifier, roles=["ROLE_OWN"])

    class _OwnLoaderHandler(AccessTokenHandlerInterface):
        @override
        async def get_user_badge_from(self, access_token: str) -> UserBadge:
            del access_token
            return UserBadge("alice", user_loader=load)

    authenticator = AccessTokenAuthenticator(
        _OwnLoaderHandler(),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
        user_provider=InMemoryUserProvider(
            {"alice": {"password": None, "roles": [], "enabled": True}}
        ),
    )

    passport = await authenticator.authenticate(_request("Bearer good"))

    assert passport.get_user_badge().get_user_loader() is load


async def test_the_scope_is_read_from_scp_when_scope_is_absent() -> None:
    authenticator = AccessTokenAuthenticator(
        _AttributesHandler({"scp": ["books:read", "books:write"]}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )

    passport = await authenticator.authenticate(_request("Bearer good"))

    assert passport.get_attribute(AccessTokenAuthenticator.SCOPE_ATTRIBUTE) == [
        "books:read",
        "books:write",
    ]


async def test_scope_wins_over_scp() -> None:
    authenticator = AccessTokenAuthenticator(
        _AttributesHandler({"scope": "books:read", "scp": ["books:write"]}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )

    passport = await authenticator.authenticate(_request("Bearer good"))

    assert passport.get_attribute(AccessTokenAuthenticator.SCOPE_ATTRIBUTE) == ["books:read"]


async def test_a_scope_list_is_joined_and_deduplicated() -> None:
    authenticator = AccessTokenAuthenticator(
        _AttributesHandler({"scope": ["books:read books:write", "books:read", 3]}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )

    passport = await authenticator.authenticate(_request("Bearer good"))

    assert passport.get_attribute(AccessTokenAuthenticator.SCOPE_ATTRIBUTE) == [
        "books:read",
        "books:write",
    ]


async def test_a_failed_authentication_is_answered_with_the_invalid_token_challenge() -> None:
    response = await _authenticator().on_authentication_failure(
        _request(), InvalidAccessTokenError()
    )

    assert response.get_status_code() == 401
    challenge = response.get_header_line("www-authenticate")
    assert challenge.startswith("Bearer")
    assert 'realm="shop"' in challenge
    assert 'error="invalid_token"' in challenge
    assert "error_description=" in challenge
    assert await response.get_body().get_contents() == b'{"error":"invalid_token"}'


async def test_the_constraint_names_the_scheme_of_the_challenge() -> None:
    constraint = FakeSenderConstraint(scheme="DPoP", parameters={"error": "use_dpop_nonce"})
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
        realm="shop",
        sender_constraint=constraint,
    )

    response = await authenticator.start(_request())

    challenge = response.get_header_line("www-authenticate")
    assert challenge.startswith("DPoP")
    assert 'realm="shop"' in challenge
    assert 'error="use_dpop_nonce"' in challenge
    assert constraint.challenged == [None]


async def test_the_constraints_parameters_override_the_authenticators() -> None:
    constraint = FakeSenderConstraint(parameters={"error_description": "bring a proof"})
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
        sender_constraint=constraint,
    )
    error = InvalidAccessTokenError()

    response = await authenticator.on_authentication_failure(_request(), error)

    challenge = response.get_header_line("www-authenticate")
    assert 'error_description="bring a proof"' in challenge
    assert constraint.challenged == [error]


async def test_resource_metadata_is_named_in_the_challenge() -> None:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
        resource_metadata_uri="https://issuer.test/.well-known/oauth-protected-resource",
    )

    response = await authenticator.start(_request())

    assert (
        'resource_metadata="https://issuer.test/.well-known/oauth-protected-resource"'
        in response.get_header_line("www-authenticate")
    )


async def test_a_resource_metadata_path_is_resolved_against_the_request() -> None:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
        resource_metadata_uri="/.well-known/oauth-protected-resource",
    )

    response = await authenticator.start(make_message(path="/api/me", query="page=2"))

    assert (
        'resource_metadata="https://example.com/.well-known/oauth-protected-resource"'
        in response.get_header_line("www-authenticate")
    )
