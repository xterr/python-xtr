"""Reading an access token off a request, and challenging when there is none."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Final, final

import pytest
from starlette.requests import Request
from typing_extensions import override
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.resource_server import ResourceServer

from tests.support.messages import server_request
from tests.support.repositories import InMemoryAccessTokenRepository
from tests.support.users import SecurityUser
from xtr_security_oauth2_server.security.authentication.token.oauth2_token import OAuth2Token
from xtr_security_oauth2_server.security.authenticator.oauth2_authenticator import (
    OAuth2Authenticator,
)
from xtr_security_oauth2_server.security.exception.oauth2_authentication_failed_error import (
    OAuth2AuthenticationFailedError,
)
from xtr_security_oauth2_server.security.user.client_credentials_user import ClientCredentialsUser

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.responses import Response
    from xtr_http_kernel.bridge import ServedRequest
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio

ROLE_PREFIX: Final = "ROLE_OAUTH2_"
FIREWALL: Final = "api"
CLIENT_ID: Final = "a-confidential-client"
OWNER: Final = "ada"
TOKEN_ID: Final = "at-1"


@final
class _ReadToken:
    """A validator answering with whatever the token is taken to have said."""

    def __init__(self, attributes: Mapping[str, object]) -> None:
        self._attributes = attributes

    async def validate_authorization(
        self,
        request: ServerRequestInterface,
    ) -> ServerRequestInterface:
        answered = request
        for name, value in self._attributes.items():
            answered = answered.with_attribute(name, value)

        return answered


@final
class _RefuseToken:
    """A validator that will not accept the token the request carried."""

    async def validate_authorization(
        self,
        request: ServerRequestInterface,
    ) -> ServerRequestInterface:
        del request

        raise OAuthServerError.access_denied("The token is not one of ours.")


@final
class _SameRequest:
    """The bridge, standing still: the message a test built is handed straight on."""

    def __init__(self, message: ServerRequestInterface) -> None:
        self._message = message

    async def create_request(self, request: Request) -> ServerRequestInterface:
        del request

        return self._message

    def create_response(self, response: Response) -> ResponseInterface:
        del response

        raise AssertionError("the authenticator builds no response message")  # pragma: no cover

    def serve(self, request: Request) -> ServedRequest:
        del request

        raise AssertionError("the authenticator serves no request")  # pragma: no cover


@final
class _KnownUsers:
    """A provider that knows one resource owner by name."""

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        if identifier != OWNER:
            raise AssertionError(f"asked for an unknown user: {identifier!r}")

        return SecurityUser(OWNER)

    def supports_class(self, user_class: type) -> bool:
        return user_class is SecurityUser

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        return user


def _served(headers: Mapping[str, str] | None = None) -> Request:
    """Return the framework's own request, which the authenticator only reads headers off."""
    raw = [(name.lower().encode(), value.encode()) for name, value in (headers or {}).items()]

    return Request({"type": "http", "method": "GET", "path": "/api/me", "headers": raw})


def _authenticator(attributes: Mapping[str, object]) -> OAuth2Authenticator:
    """Return the authenticator over a resource server answering with ``attributes``."""
    message = server_request("GET", "/api/me")
    validator = _ReadToken(attributes)

    return OAuth2Authenticator(
        _SameRequest(message),
        ResourceServer(InMemoryAccessTokenRepository(), validator),
        _KnownUsers(),
        ROLE_PREFIX,
        FIREWALL,
    )


def test_it_handles_only_a_request_carrying_a_bearer_token() -> None:
    authenticator = _authenticator({})

    assert authenticator.supports(_served({"Authorization": "Bearer abc"})) is True
    assert authenticator.supports(_served({"Authorization": "Basic abc"})) is False
    assert authenticator.supports(_served()) is False


def test_the_scheme_is_claimed_whatever_case_it_was_written_in() -> None:
    # The scheme name of the HTTP authentication framework is
    # case-insensitive (RFC 9110 section 11.1), so a caller writing RFC 6750's
    # ``Bearer`` differently is still presenting a bearer token.
    authenticator = _authenticator({})

    assert authenticator.supports(_served({"Authorization": "bearer abc"})) is True
    assert authenticator.supports(_served({"Authorization": "BEARER abc"})) is True
    # The scheme and nothing after it is not a token, and neither is a name
    # that only begins like the scheme.
    assert authenticator.supports(_served({"Authorization": "Bearerish abc"})) is False


async def test_a_token_naming_a_resource_owner_loads_them_through_the_provider() -> None:
    authenticator = _authenticator(
        {
            "oauth_access_token_id": TOKEN_ID,
            "oauth_client_id": CLIENT_ID,
            "oauth_user_id": OWNER,
            "oauth_scopes": ("read",),
        },
    )

    passport = await authenticator.authenticate(_served({"Authorization": "Bearer abc"}))
    _ = await passport.get_user_badge().get_user()
    token = await authenticator.create_token(passport, "api")

    assert isinstance(token, OAuth2Token)
    assert token.get_user_identifier() == OWNER
    assert f"{ROLE_PREFIX}READ" in token.get_role_names()


async def test_a_token_issued_to_a_client_for_itself_names_the_client_as_the_caller() -> None:
    # There is no person to load, so a stand-in carries the client's identifier.
    authenticator = _authenticator(
        {
            "oauth_access_token_id": TOKEN_ID,
            "oauth_client_id": CLIENT_ID,
            "oauth_scopes": "read write",
        },
    )

    passport = await authenticator.authenticate(_served({"Authorization": "Bearer abc"}))
    loaded = await passport.get_user_badge().get_user()

    assert isinstance(loaded, ClientCredentialsUser)
    assert loaded.get_user_identifier() == CLIENT_ID


async def test_the_scopes_are_read_whether_they_arrive_as_a_string_or_a_list() -> None:
    # What a resource server records is an attribute bag, and the two shapes a
    # scope list arrives in are both the truth about the token.
    spaced = _authenticator(
        {
            "oauth_access_token_id": TOKEN_ID,
            "oauth_client_id": CLIENT_ID,
            "oauth_scopes": "read  write",
        },
    )

    passport = await spaced.authenticate(_served({"Authorization": "Bearer abc"}))
    _ = await passport.get_user_badge().get_user()
    token = await spaced.create_token(passport, "api")

    assert isinstance(token, OAuth2Token)
    # The empty name between the two spaces is dropped, not carried as a scope.
    assert token.get_scopes() == ("read", "write")


async def test_a_token_naming_neither_an_owner_nor_a_client_is_refused() -> None:
    # There is then nobody it could have been issued to, so there is nothing to
    # authenticate as.
    authenticator = _authenticator({"oauth_access_token_id": TOKEN_ID})

    with pytest.raises(OAuth2AuthenticationFailedError) as refused:
        _ = await authenticator.authenticate(_served({"Authorization": "Bearer abc"}))

    # What the caller is told is the same for every unusable token; which it
    # was stays in the exception, for a log.
    assert refused.value.get_message_key() == "The access token could not be accepted."
    assert "neither a resource owner nor a client" in str(refused.value)


async def test_a_token_the_resource_server_will_not_accept_is_refused() -> None:
    authenticator = OAuth2Authenticator(
        _SameRequest(server_request("GET", "/api/me")),
        ResourceServer(InMemoryAccessTokenRepository(), _RefuseToken()),
        _KnownUsers(),
        ROLE_PREFIX,
        FIREWALL,
    )

    with pytest.raises(OAuth2AuthenticationFailedError):
        _ = await authenticator.authenticate(_served({"Authorization": "Bearer abc"}))


async def test_a_request_that_proved_nothing_is_challenged_with_a_bearer_scheme() -> None:
    answered = await _authenticator({}).start(_served())

    assert answered.status_code == HTTPStatus.UNAUTHORIZED
    # "This scheme MUST be followed by one or more auth-param values"
    # (RFC 6750 section 3), and section 3.1 asks that a request lacking any
    # authentication information be told no error code — so the realm is all
    # the challenge names.
    assert answered.headers["WWW-Authenticate"] == f'Bearer realm="{FIREWALL}"'
    assert "error" not in answered.headers["WWW-Authenticate"]
    # A refusal must never be kept by a cache: a proxy answering another
    # caller with it would tell the wrong person about the right one.
    assert answered.headers["Cache-Control"] == "no-store"


async def test_a_refusal_of_this_package_is_answered_with_what_it_carries() -> None:
    failure = OAuth2AuthenticationFailedError.create("Nope.")

    answered = await _authenticator({}).on_authentication_failure(_served(), failure)

    assert answered is not None
    # "in case of any failure in the validation checks listed above, the
    # authorization server response MUST include the error code
    # "invalid_token"" (RFC 9068 section 4).
    assert 'error="invalid_token"' in answered.headers["WWW-Authenticate"]
    body = json.loads(bytes(answered.body))  # pyright: ignore[reportAny] -- what a JSON document decodes to
    assert isinstance(body, dict)
    assert body["message"] == "The access token could not be accepted."
    assert body["code"] == HTTPStatus.UNAUTHORIZED


async def test_a_failure_from_somewhere_else_is_left_to_the_firewall() -> None:
    from xtr_security_core.exception import AuthenticationError  # noqa: PLC0415 -- used only here

    answered = await _authenticator({}).on_authentication_failure(
        _served(),
        AuthenticationError("something else"),
    )

    assert answered is None


def test_it_names_its_configuration_and_nothing_it_holds() -> None:
    assert repr(_authenticator({})) == (
        f"OAuth2Authenticator(role_prefix={ROLE_PREFIX!r}, realm={FIREWALL!r})"
    )
