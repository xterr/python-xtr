"""The exception listener answers a request's failure from its firewall's parts."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from starlette.responses import Response as FrameworkResponse
from typing_extensions import override
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_kernel import ExceptionEvent
from xtr_http_kernel.bridge import Response as KernelResponse
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_http_message import Response as PureResponse
from xtr_security_core.authentication.authentication_trust_resolver import (
    AuthenticationTrustResolver,
)
from xtr_security_core.authentication.token.remember_me_token import RememberMeToken
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.authorization.voter.access import Access
from xtr_security_core.authorization.voter.vote import Vote
from xtr_security_core.exception import (
    AccessDeniedError,
    BadCredentialsError,
    DisabledError,
    InsufficientAuthenticationError,
)
from xtr_security_core.user import InMemoryUser

from tests.support.messages import make_message
from tests.support.recording_logger import RecordingLogger
from xtr_security_http._security_state import SecurityState, security_state_of
from xtr_security_http.authenticator.token import PostAuthenticationToken
from xtr_security_http.entry_point.fallback_authentication_entry_point_interface import (
    FallbackAuthenticationEntryPointInterface,
)
from xtr_security_http.exception import InvalidAccessTokenError, LogoutError
from xtr_security_http.firewall.exception_listener import ExceptionListener
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.util.target_path import get_target_path

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError

    from xtr_security_http.authorization.access_denied_handler_interface import (
        AccessDeniedHandlerInterface,
    )
    from xtr_security_http.entry_point.authentication_entry_point_interface import (
        AuthenticationEntryPointInterface,
    )
    from xtr_security_http.entry_point.re_authentication_entry_point_interface import (
        ReAuthenticationEntryPointInterface,
    )

pytestmark = pytest.mark.anyio


@final
class _ChallengingEntryPoint:
    """Answers with the response it was built to return."""

    def __init__(self, response: ResponseInterface) -> None:
        self._response = response

    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        del request, error
        return self._response


@final
class _RecordingEntryPoint:
    """Records the error it was started with, answering with a bare 401."""

    def __init__(self) -> None:
        self.started_with: AuthenticationError | None = None

    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        del request
        self.started_with = error
        return ResponseFactory().create_response(401)


@final
class _FallbackEntryPoint(FallbackAuthenticationEntryPointInterface):
    """Stands in as an entry point, answering with a bare 401."""

    @override
    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        del request, error
        return ResponseFactory().create_response(401)


@final
class _ReAuthenticationEntryPoint:
    """Records the re-authentication it starts, answering with a bare 401."""

    def __init__(self) -> None:
        self.started: tuple[ServerRequestInterface, TokenInterface] | None = None

    async def start_re_authentication(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface:
        self.started = (request, token)
        return ResponseFactory().create_response(401)


@final
class _DualEntryPoint:
    """An entry point that also starts a re-authentication."""

    def __init__(self) -> None:
        self.started: tuple[ServerRequestInterface, TokenInterface] | None = None

    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        del request, error
        return ResponseFactory().create_response(401)

    async def start_re_authentication(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface:
        self.started = (request, token)
        return ResponseFactory().create_response(401)


@final
class _RecordingHandler:
    """Records the denial it was handed, answering as it was built to."""

    def __init__(self, response: ResponseInterface | None) -> None:
        self._response = response
        self.handled: AccessDeniedError | None = None

    async def handle(
        self, request: ServerRequestInterface, error: AccessDeniedError
    ) -> ResponseInterface | None:
        del request
        self.handled = error
        return self._response


def _listener(  # noqa: PLR0913 -- a test builder, naming every overridable part of the listener
    *,
    entry_point: AuthenticationEntryPointInterface | None = None,
    error_page: str | None = None,
    access_denied_handler: AccessDeniedHandlerInterface | None = None,
    scope_denied_handler: AccessDeniedHandlerInterface | None = None,
    logger: LoggerInterface | None = None,
    stateless: bool = True,
    re_authentication_entry_point: ReAuthenticationEntryPointInterface | None = None,
) -> ExceptionListener:
    """Build the listener of the ``api`` firewall, overridable part by part."""
    return ExceptionListener(
        TokenStorage(),
        AuthenticationTrustResolver(),
        ResponseFactory(),
        StarletteHttpFactory(),
        "api",
        entry_point=entry_point,
        error_page=error_page,
        access_denied_handler=access_denied_handler,
        scope_denied_handler=scope_denied_handler,
        logger=logger,
        stateless=stateless,
        re_authentication_entry_point=re_authentication_entry_point,
    )


def _event(
    error: BaseException,
    bag: dict[str, object] | None = None,
    request: ServerRequestInterface | None = None,
) -> ExceptionEvent:
    # ``bag if bag is not None else {}``, never ``bag or {}``: an empty bag is
    # still the bag the caller parked its state on, and a truthiness check
    # would swap it for a fresh one nobody shares.
    return ExceptionEvent(
        request if request is not None else make_message(),
        bag if bag is not None else {},
        error,
    )


def _state(error: BaseException) -> tuple[ExceptionEvent, SecurityState]:
    """Return an event carrying ``error`` over a fresh security state, with the state beside it."""
    bag: dict[str, object] = {}
    return _event(error, bag), security_state_of(bag)


def _full_fledged(bag: dict[str, object]) -> None:
    """Park a fully authenticated token on the state in ``bag``."""
    security_state_of(bag).token = PostAuthenticationToken(
        InMemoryUser("alice"), "api", ["ROLE_USER"]
    )


def _recency_denial(attribute: str = "IS_AUTHENTICATED_RECENTLY") -> AccessDeniedError:
    """Return a denial a recency vote asked a re-authentication for."""
    vote = Vote(result=Access.DENIED)
    vote.request_re_authentication(attribute)
    decision = AccessDecision(is_granted=False, votes=[vote])
    return AccessDeniedError(attributes=(attribute,), access_decision=decision)


async def test_a_non_security_exception_is_left_alone() -> None:
    event = _event(RuntimeError("boom"))

    await _listener().on_exception(event)

    assert event.response is None


async def test_a_logout_error_is_refused() -> None:
    event = _event(LogoutError("Invalid CSRF token."))

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403


async def test_a_logout_error_is_logged_when_a_logger_is_given() -> None:
    logger = RecordingLogger()
    event = _event(LogoutError("Invalid CSRF token."))

    await _listener(logger=logger).on_exception(event)

    assert logger.messages("info") == [
        "A logout error was thrown; refusing the request.",
    ]


async def test_a_security_error_in_the_cause_chain_is_answered() -> None:
    failure = RuntimeError("the handler failed")
    failure.__cause__ = BadCredentialsError()

    event = _event(failure)

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401


async def test_the_first_security_link_in_the_chain_is_answered() -> None:
    outer = RuntimeError("earlier")
    outer.__cause__ = BadCredentialsError()
    outer.__cause__.__cause__ = AccessDeniedError(attributes=("ROLE_ADMIN",))

    event = _event(outer)

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401


async def test_an_authentication_error_without_an_entry_point_is_a_bare_challenge() -> None:
    event = _event(BadCredentialsError())

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401
    assert event.response.headers["www-authenticate"] == "Bearer"
    assert event.response.headers["cache-control"] == "no-store"
    assert event.response.headers["pragma"] == "no-cache"
    assert isinstance(event.response, KernelResponse)
    assert await event.response.get_body().get_contents() == b'{"error":"unauthorized"}'


async def test_an_authentication_error_is_answered_by_the_entry_point() -> None:
    answered = ResponseFactory().create_response(302).with_header("location", "/login")
    event = _event(BadCredentialsError())

    await _listener(entry_point=_ChallengingEntryPoint(answered)).on_exception(event)

    assert event.response is answered


async def test_a_stateless_firewall_saves_no_target_path() -> None:
    session = Session(MemorySessionStorage())
    event, state = _state(BadCredentialsError())
    state.attributes[SecurityRequestAttributes.SESSION] = session

    await _listener(entry_point=_RecordingEntryPoint()).on_exception(event)

    assert await get_target_path(session, "api") is None


async def test_a_stateful_firewall_saves_the_target_path_of_a_safe_request() -> None:
    session = Session(MemorySessionStorage())
    request = make_message(path="/protected", query="page=2")
    event = _event(BadCredentialsError(), {}, request)
    state = security_state_of(event.state)
    state.attributes[SecurityRequestAttributes.SESSION] = session

    await _listener(stateless=False, entry_point=_RecordingEntryPoint()).on_exception(event)

    assert await get_target_path(session, "api") == "https://example.com/protected?page=2"


async def test_a_stateful_firewall_saves_no_target_path_for_an_unsafe_method() -> None:
    session = Session(MemorySessionStorage())
    request = make_message(method="POST", path="/protected")
    event = _event(BadCredentialsError(), {}, request)
    state = security_state_of(event.state)
    state.attributes[SecurityRequestAttributes.SESSION] = session

    await _listener(stateless=False, entry_point=_RecordingEntryPoint()).on_exception(event)

    assert await get_target_path(session, "api") is None


async def test_a_stateful_firewall_saves_no_target_path_for_an_xml_http_request() -> None:
    session = Session(MemorySessionStorage())
    request = make_message(path="/protected", headers={"x-requested-with": "XMLHttpRequest"})
    event = _event(BadCredentialsError(), {}, request)
    state = security_state_of(event.state)
    state.attributes[SecurityRequestAttributes.SESSION] = session

    await _listener(stateless=False, entry_point=_RecordingEntryPoint()).on_exception(event)

    assert await get_target_path(session, "api") is None


async def test_a_fallback_entry_point_gets_no_target_path_saved() -> None:
    session = Session(MemorySessionStorage())
    request = make_message(path="/protected")
    event = _event(BadCredentialsError(), {}, request)
    state = security_state_of(event.state)
    state.attributes[SecurityRequestAttributes.SESSION] = session

    await _listener(stateless=False, entry_point=_FallbackEntryPoint()).on_exception(event)

    assert await get_target_path(session, "api") is None


async def test_an_account_status_error_clears_the_token() -> None:
    storage = TokenStorage()
    token = PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    storage.set_token(token)
    listener = ExceptionListener(
        storage,
        AuthenticationTrustResolver(),
        ResponseFactory(),
        StarletteHttpFactory(),
        "api",
        entry_point=_RecordingEntryPoint(),
    )
    event, state = _state(DisabledError())
    state.token = token

    await listener.on_exception(event)

    assert storage.get_token() is None
    assert state.token is None


async def test_a_non_account_authentication_error_keeps_the_token() -> None:
    storage = TokenStorage()
    token = PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    storage.set_token(token)
    listener = ExceptionListener(
        storage,
        AuthenticationTrustResolver(),
        ResponseFactory(),
        StarletteHttpFactory(),
        "api",
        entry_point=_RecordingEntryPoint(),
    )
    event, state = _state(BadCredentialsError())
    state.token = token

    await listener.on_exception(event)

    assert storage.get_token() is token


async def test_a_denial_from_an_anonymous_caller_starts_the_entry_point() -> None:
    entry_point = _RecordingEntryPoint()
    event = _event(AccessDeniedError(attributes=("ROLE_ADMIN",)))

    await _listener(entry_point=entry_point).on_exception(event)

    assert isinstance(entry_point.started_with, InsufficientAuthenticationError)


async def test_a_denial_from_an_anonymous_caller_names_the_parked_authentication_error() -> None:
    entry_point = _RecordingEntryPoint()
    event, state = _state(AccessDeniedError(attributes=("ROLE_ADMIN",)))
    parked = InvalidAccessTokenError("The token is not known.")
    state.attributes[SecurityRequestAttributes.AUTHENTICATION_ERROR] = parked

    await _listener(entry_point=entry_point).on_exception(event)

    assert entry_point.started_with is parked


async def test_a_denial_from_an_anonymous_caller_without_an_entry_point_challenges() -> None:
    event = _event(AccessDeniedError(attributes=("ROLE_ADMIN",)))

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401


async def test_a_full_fledged_denial_without_a_handler_is_an_uncached_403() -> None:
    bag: dict[str, object] = {}
    _full_fledged(bag)
    event = _event(AccessDeniedError(attributes=("ROLE_ADMIN",)), bag)

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403
    assert event.response.headers["cache-control"] == "no-store"
    assert event.response.headers["pragma"] == "no-cache"


async def test_a_full_fledged_denial_is_answered_by_the_access_denied_handler() -> None:
    answered = ResponseFactory().create_response(418)
    handler = _RecordingHandler(answered)
    bag: dict[str, object] = {}
    _full_fledged(bag)
    event = _event(AccessDeniedError(attributes=("ROLE_ADMIN",)), bag)

    await _listener(access_denied_handler=handler).on_exception(event)

    assert event.response is answered
    assert handler.handled is not None


async def test_a_handler_answering_none_falls_through_to_the_403() -> None:
    handler = _RecordingHandler(None)
    bag: dict[str, object] = {}
    _full_fledged(bag)
    event = _event(AccessDeniedError(attributes=("ROLE_ADMIN",)), bag)

    await _listener(access_denied_handler=handler).on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403


async def test_a_configured_error_page_falls_through_to_the_403() -> None:
    """The error page is vacant: no sub-request mechanism, so no rendering."""
    bag: dict[str, object] = {}
    _full_fledged(bag)
    event = _event(AccessDeniedError(attributes=("ROLE_ADMIN",)), bag)

    await _listener(error_page="/403").on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403


async def test_a_recency_denial_starts_a_re_authentication_for_a_full_fledged_caller() -> None:
    re_authentication = _ReAuthenticationEntryPoint()
    bag: dict[str, object] = {}
    _full_fledged(bag)
    token = security_state_of(bag).token
    event = _event(_recency_denial(), bag)

    await _listener(re_authentication_entry_point=re_authentication).on_exception(event)

    assert re_authentication.started is not None
    asked, asked_token = re_authentication.started
    assert asked_token is token
    assert asked.get_attribute(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE) == (
        "IS_AUTHENTICATED_RECENTLY"
    )


async def test_a_re_authentication_saves_the_target_path_of_a_stateful_firewall() -> None:
    session = Session(MemorySessionStorage())
    re_authentication = _ReAuthenticationEntryPoint()
    bag: dict[str, object] = {}
    _full_fledged(bag)
    state = security_state_of(bag)
    state.attributes[SecurityRequestAttributes.SESSION] = session
    request = make_message(path="/protected")
    event = _event(_recency_denial(), bag, request)

    listener = _listener(
        stateless=False,
        re_authentication_entry_point=re_authentication,
    )
    await listener.on_exception(event)

    assert await get_target_path(session, "api") == "https://example.com/protected"


async def test_an_entry_point_that_also_re_authenticates_is_used_without_configuration() -> None:
    dual = _DualEntryPoint()
    bag: dict[str, object] = {}
    _full_fledged(bag)
    event = _event(_recency_denial(), bag)

    await _listener(entry_point=dual).on_exception(event)

    assert dual.started is not None


async def test_a_remembered_caller_is_re_authenticated_rather_than_refused() -> None:
    re_authentication = _ReAuthenticationEntryPoint()
    bag: dict[str, object] = {}
    security_state_of(bag).token = RememberMeToken(InMemoryUser("alice"), "api")
    event = _event(_recency_denial(), bag)

    await _listener(re_authentication_entry_point=re_authentication).on_exception(event)

    assert re_authentication.started is not None


async def test_a_denial_no_vote_asked_to_re_authenticate_is_refused() -> None:
    bag: dict[str, object] = {}
    _full_fledged(bag)
    event = _event(AccessDeniedError(attributes=("ROLE_ADMIN",)), bag)

    await _listener(re_authentication_entry_point=_ReAuthenticationEntryPoint()).on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403


async def test_a_denial_of_several_attributes_is_not_re_authenticated() -> None:
    bag: dict[str, object] = {}
    _full_fledged(bag)
    vote = Vote(result=Access.DENIED)
    vote.request_re_authentication("IS_AUTHENTICATED_RECENTLY")
    error = AccessDeniedError(
        attributes=("ROLE_ADMIN", "IS_AUTHENTICATED_RECENTLY"),
        access_decision=AccessDecision(is_granted=False, votes=[vote]),
    )
    event = _event(error, bag)

    await _listener(re_authentication_entry_point=_ReAuthenticationEntryPoint()).on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403


async def test_a_closure_denial_is_re_authenticated_whatever_attribute_the_vote_names() -> None:
    def check(subject: object) -> bool:
        del subject
        return False

    re_authentication = _ReAuthenticationEntryPoint()
    bag: dict[str, object] = {}
    _full_fledged(bag)
    vote = Vote(result=Access.DENIED)
    vote.request_re_authentication("IS_AUTHENTICATED_RECENTLY")
    error = AccessDeniedError(
        attributes=(check,),
        access_decision=AccessDecision(is_granted=False, votes=[vote]),
    )
    event = _event(error, bag)

    await _listener(re_authentication_entry_point=re_authentication).on_exception(event)

    assert re_authentication.started is not None


async def test_a_pure_message_from_an_entry_point_is_converted_to_what_the_event_accepts() -> None:
    pure = PureResponse(401, None, None, "1.1").with_header("location", "/login")
    event = _event(BadCredentialsError())

    await _listener(entry_point=_ChallengingEntryPoint(pure)).on_exception(event)

    assert event.response is not None
    assert event.response is not pure
    assert isinstance(event.response, FrameworkResponse)
    assert event.response.status_code == 401
    assert event.response.headers["location"] == "/login"


async def test_a_kernel_response_from_an_entry_point_is_sent_as_it_is() -> None:
    dual = ResponseFactory().create_response(401).with_header("location", "/login")
    event = _event(BadCredentialsError())

    await _listener(entry_point=_ChallengingEntryPoint(dual)).on_exception(event)

    assert event.response is dual


async def test_the_branches_are_logged_when_a_logger_is_given() -> None:
    logger = RecordingLogger()
    event = _event(BadCredentialsError())

    await _listener(logger=logger).on_exception(event)

    assert logger.messages("info") == [
        "An authentication error was thrown; starting the entry point.",
    ]
    assert logger.messages("notice") == [
        "No entry point configured; answering a bare 401.",
    ]
