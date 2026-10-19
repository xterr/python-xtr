"""The remember-me authenticator: a returning cookie spent into a login."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.remember_me_token import RememberMeToken
from xtr_security_core.exception import (
    AuthenticationError,
    BadMethodCallError,
    CookieTheftError,
    UserNotFoundError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from tests.support.recording_logger import RecordingLogger
from tests.support.remember_me import RecordingHandler
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.passport.self_validating_passport import (
    SelfValidatingPassport,
)
from xtr_security_http.authenticator.remember_me_authenticator import RememberMeAuthenticator
from xtr_security_http.remember_me import RememberMeCookie, RememberMeDetails
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface

pytestmark = pytest.mark.anyio


@final
class _RecordingTokenStorage:
    """A token storage that answers what it was built with."""

    __slots__ = ("_token",)

    def __init__(self, token: TokenInterface | None = None) -> None:
        self._token = token

    def get_token(self) -> TokenInterface | None:
        """Return the token this storage was built with."""
        return self._token

    def set_token(self, token: TokenInterface | None) -> None:
        """Keep ``token``; the authenticator never stores one itself."""
        self._token = token


def _request(
    *,
    cookie: str | None = None,
    staged: RememberMeCookie | None = None,
    reasons: UnsupportedReasons | None = None,
) -> ServerRequestInterface:
    """Build a request carrying a cookie, a staged cookie and the reasons, as asked."""
    message = make_message()
    if cookie is not None:
        message = message.with_cookie_params({"REMEMBERME": cookie})
    bag: dict[str, object] = {}
    message = message.with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    if staged is not None:
        security_state_of(bag).attributes[SecurityRequestAttributes.REMEMBER_ME_COOKIE] = staged
    if reasons is not None:
        message = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)
    return message


def _authenticator(
    handler: RecordingHandler,
    storage: TokenStorageInterface,
    logger: RecordingLogger | None = None,
) -> RememberMeAuthenticator:
    return RememberMeAuthenticator(handler, storage, "REMEMBERME", logger)


def test_the_authenticator_is_interactive_as_the_flow_always_was() -> None:
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage())

    assert authenticator.is_interactive() is True


def test_a_request_with_no_stored_token_and_a_cookie_is_handled_lazily() -> None:
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage())

    assert authenticator.supports(_request(cookie="the-cookie")) is None


def test_a_request_whose_storage_already_holds_a_token_is_left_alone() -> None:
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage(NullToken()))
    reasons = UnsupportedReasons()

    assert authenticator.supports(_request(cookie="the-cookie", reasons=reasons)) is False
    assert reasons.all() == ("a token is already stored, so the request is already authenticated",)


def test_a_request_clearing_the_cookie_does_not_spend_it() -> None:
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage())
    reasons = UnsupportedReasons()

    supported = authenticator.supports(
        _request(cookie="the-cookie", staged=RememberMeCookie("REMEMBERME", None), reasons=reasons),
    )

    assert supported is False
    assert reasons.all() == ('the "REMEMBERME" cookie is being cleared by this request',)


def test_a_request_with_no_cookie_is_not_handled() -> None:
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage())
    reasons = UnsupportedReasons()

    assert authenticator.supports(_request(reasons=reasons)) is False
    assert reasons.all() == ('the request has no "REMEMBERME" cookie',)


def test_a_request_with_an_empty_cookie_is_not_handled() -> None:
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage())
    reasons = UnsupportedReasons()

    assert authenticator.supports(_request(cookie="", reasons=reasons)) is False
    assert reasons.all() == ('the "REMEMBERME" cookie is empty or not a scalar',)


async def test_authenticate_builds_a_self_validating_passport_around_the_spent_cookie() -> None:
    user = InMemoryUser("ada")
    handler = RecordingHandler(user)
    authenticator = _authenticator(handler, _RecordingTokenStorage())
    details = RememberMeDetails("ada", 123, "the-value")
    request = _request(cookie=str(details))

    passport = await authenticator.authenticate(request)

    assert isinstance(passport, SelfValidatingPassport)
    assert await passport.get_user() is user
    recorded_request, recorded_details = handler.consumed[0]
    assert recorded_request is request
    assert recorded_details.get_user_identifier() == details.get_user_identifier()
    assert recorded_details.get_expires() == details.get_expires()
    assert recorded_details.get_value() == details.get_value()


async def test_authenticate_refuses_a_request_that_carries_no_cookie() -> None:
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage())

    with pytest.raises(BadMethodCallError, match="No remember-me cookie is found"):
        _ = await authenticator.authenticate(_request())


async def test_authenticate_lets_a_malformed_cookie_be_the_details_own_refusal() -> None:
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage())

    with pytest.raises(AuthenticationError, match="invalid data"):
        _ = await authenticator.authenticate(_request(cookie="nonsense"))


async def test_create_token_mints_a_remembered_token_for_the_firewall() -> None:
    user = InMemoryUser("ada")
    handler = RecordingHandler(user)
    authenticator = _authenticator(handler, _RecordingTokenStorage())
    passport = await authenticator.authenticate(
        _request(cookie=str(RememberMeDetails("ada", 123, "the-value"))),
    )

    token = await authenticator.create_token(passport, "main")

    assert isinstance(token, RememberMeToken)
    assert token.get_user_identifier() == "ada"
    assert token.get_firewall_name() == "main"


async def test_a_failure_is_logged_by_what_it_says_about_the_cookie() -> None:
    logger = RecordingLogger()
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage(), logger)

    response = await authenticator.on_authentication_failure(
        _request(),
        UserNotFoundError("unknown"),
    )

    assert response is None
    assert logger.messages("info") == ["User for remember-me cookie not found."]


async def test_a_plain_failure_is_logged_at_debug() -> None:
    logger = RecordingLogger()
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage(), logger)

    response = await authenticator.on_authentication_failure(
        _request(),
        AuthenticationError("no"),
    )

    assert response is None
    assert logger.messages("debug") == ["Remember me authentication failed."]


async def test_a_theft_is_not_logged_here_the_handler_already_raised_it() -> None:
    logger = RecordingLogger()
    authenticator = _authenticator(RecordingHandler(), _RecordingTokenStorage(), logger)

    response = await authenticator.on_authentication_failure(
        _request(),
        CookieTheftError("spent"),
    )

    assert response is None
    assert logger.records == []
