"""The authenticator manager runs the fixed authentication sequence."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, cast, final

import pytest
from typing_extensions import override
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
    InvalidArgumentError,
    UserNotFoundError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.dispatchers import RecordingDispatcher
from tests.support.messages import make_message
from tests.support.users import loader
from xtr_security_http._security_state import SecurityState
from xtr_security_http.authentication.authenticator_manager import AuthenticatorManager
from xtr_security_http.authentication.expose_security_level import ExposeSecurityLevel
from xtr_security_http.authentication.user_authenticator_interface import UserAuthenticatorInterface
from xtr_security_http.authenticator.abstract_authenticator import AbstractAuthenticator
from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.credentials import PasswordCredentials
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.interactive_login_event import InteractiveLoginEvent
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.exception import InvalidAccessTokenError
from xtr_security_http.security_events import SecurityEvents
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface

pytestmark = pytest.mark.anyio

_EventT = TypeVar("_EventT")


@final
class _Authenticator(AbstractAuthenticator):
    def __init__(self, *, supports: bool | None = True, identifier: str = "alice") -> None:
        self._supports = supports
        self._identifier = identifier
        self.supports_calls = 0
        self.authentications = 0

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        self.supports_calls += 1
        return self._supports

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        del request
        self.authentications += 1
        return Passport(
            UserBadge(self._identifier, user_loader=loader(roles=("ROLE_USER",))),
        )


@final
class _NoTokenAuthenticator(AbstractAuthenticator):
    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        return None

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        del request
        raise BadCredentialsError("no token")


@final
class _BadTokenAuthenticator(AbstractAuthenticator):
    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        return None

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        del request
        raise InvalidAccessTokenError


@final
class _InteractiveAuthenticator(AbstractAuthenticator):
    """An authenticator a user actively logs in through — or claims to."""

    def __init__(self, *, interactive: bool = True) -> None:
        self._interactive = interactive

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        return True

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        del request
        return Passport(
            UserBadge("alice", user_loader=loader(roles=("ROLE_USER",))),
        )

    def is_interactive(self) -> bool:
        return self._interactive


@final
class _NotAnAuthenticator:
    """Something an application wired in place of an authenticator by mistake."""

    def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        return True


async def _authenticate(manager: AuthenticatorManager) -> ResponseInterface | None:
    """Run the manager the way the firewall runner does: both passes over one state."""
    state = SecurityState()
    message = make_message()
    _ = manager.supports(message, state)
    return await manager.authenticate_request(message, state)


async def test_a_successful_authentication_stores_the_token() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager([_Authenticator()], storage, RecordingDispatcher(), "api")

    response = await _authenticate(manager)

    assert response is None
    token = storage.get_token()
    assert token is not None
    assert token.get_user_identifier() == "alice"


async def test_the_check_passport_and_success_events_are_dispatched() -> None:
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager([_Authenticator()], TokenStorage(), dispatcher, "api")

    _ = await _authenticate(manager)

    kinds = [type(event) for event in dispatcher.events]
    assert CheckPassportEvent in kinds
    assert AuthenticationSuccessEvent in kinds


async def test_supports_reports_true_none_or_false() -> None:
    storage = TokenStorage()
    dispatcher = RecordingDispatcher()
    eager = AuthenticatorManager([_Authenticator(supports=True)], storage, dispatcher, "api")
    lazy = AuthenticatorManager([_Authenticator(supports=None)], storage, dispatcher, "api")
    none = AuthenticatorManager([_Authenticator(supports=False)], storage, dispatcher, "api")
    empty = AuthenticatorManager([], storage, dispatcher, "api")
    mixed = AuthenticatorManager(
        [_Authenticator(supports=None), _Authenticator(supports=True)],
        storage,
        dispatcher,
        "api",
    )

    assert eager.supports(make_message(), SecurityState()) is True
    assert lazy.supports(make_message(), SecurityState()) is None
    assert none.supports(make_message(), SecurityState()) is False
    assert empty.supports(make_message(), SecurityState()) is False
    # One eager supporter among lazy ones settles it: the pass reports True.
    assert mixed.supports(make_message(), SecurityState()) is True


async def test_the_supports_pass_parks_both_handoff_keys() -> None:
    supporter = _Authenticator(supports=True)
    skipper = _Authenticator(supports=False)
    manager = AuthenticatorManager(
        [supporter, skipper],
        TokenStorage(),
        RecordingDispatcher(),
        "api",
    )
    state = SecurityState()

    _ = manager.supports(make_message(), state)

    assert state.attributes[SecurityRequestAttributes.AUTHENTICATORS] == (supporter,)
    assert state.attributes[SecurityRequestAttributes.SKIPPED_AUTHENTICATORS] == (skipper,)


async def test_authenticate_request_consumes_the_handoff_once() -> None:
    storage = TokenStorage()
    authenticator = _Authenticator()
    manager = AuthenticatorManager([authenticator], storage, RecordingDispatcher(), "api")
    state = SecurityState()
    message = make_message()
    _ = manager.supports(message, state)

    _ = await manager.authenticate_request(message, state)
    _ = await manager.authenticate_request(message, state)

    assert SecurityRequestAttributes.AUTHENTICATORS not in state.attributes
    assert SecurityRequestAttributes.SKIPPED_AUTHENTICATORS not in state.attributes
    assert authenticator.authentications == 1


async def test_authenticate_request_without_a_supports_pass_stays_anonymous() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager([_Authenticator()], storage, RecordingDispatcher(), "api")

    assert await manager.authenticate_request(make_message(), SecurityState()) is None
    assert storage.get_token() is None


async def test_authenticate_request_does_not_re_run_the_full_supports_pass() -> None:
    supporter = _Authenticator(supports=True)
    skipper = _Authenticator(supports=False)
    manager = AuthenticatorManager(
        [supporter, skipper],
        TokenStorage(),
        RecordingDispatcher(),
        "api",
    )
    state = SecurityState()
    message = make_message()
    _ = manager.supports(message, state)

    _ = await manager.authenticate_request(message, state)

    # The skipped one is asked by the supports pass alone; a supporter is
    # re-checked once, never the whole list again.
    assert skipper.supports_calls == 1
    assert supporter.supports_calls == 2


async def test_an_authenticator_that_is_no_authenticator_is_refused() -> None:
    manager = AuthenticatorManager(
        [cast("AuthenticatorInterface", cast("object", _NotAnAuthenticator()))],
        TokenStorage(),
        RecordingDispatcher(),
        "api",
    )

    with pytest.raises(InvalidArgumentError):
        _ = manager.supports(make_message(), SecurityState())


async def test_a_lazy_no_token_authenticator_abstains() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager([_NoTokenAuthenticator()], storage, RecordingDispatcher(), "api")

    response = await _authenticate(manager)

    assert response is None
    assert storage.get_token() is None


async def test_a_bad_token_is_answered_without_raising() -> None:
    storage = TokenStorage()
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager([_BadTokenAuthenticator()], storage, dispatcher, "api")

    response = await _authenticate(manager)

    assert response is None
    assert storage.get_token() is None
    failures = [event for event in dispatcher.events if isinstance(event, LoginFailureEvent)]
    assert len(failures) == 1
    assert isinstance(failures[0].get_exception(), InvalidAccessTokenError)


async def test_a_failure_parks_its_masked_error_on_the_state() -> None:
    state = SecurityState()
    manager = AuthenticatorManager(
        [_BadTokenAuthenticator()],
        TokenStorage(),
        RecordingDispatcher(),
        "api",
        expose_security_errors=ExposeSecurityLevel.NONE,
    )
    message = make_message()
    _ = manager.supports(message, state)

    _ = await manager.authenticate_request(message, state)

    # The masked error rides the state — the transport the exception listener
    # reads when the access decision denies the anonymous request.
    # An insensitive error rides unmasked; a sensitive one would ride masked.
    parked = state.attributes[SecurityRequestAttributes.AUTHENTICATION_ERROR]
    assert isinstance(parked, InvalidAccessTokenError)


async def test_a_false_authenticator_is_skipped() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager(
        [_Authenticator(supports=False), _Authenticator(identifier="bob")],
        storage,
        RecordingDispatcher(),
        "api",
    )

    _ = await _authenticate(manager)

    token = storage.get_token()
    assert token is not None
    assert token.get_user_identifier() == "bob"


async def test_a_handled_failure_without_a_response_tries_the_next_authenticator() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager(
        [_BadTokenAuthenticator(), _Authenticator(identifier="bob")],
        storage,
        RecordingDispatcher(),
        "api",
    )

    response = await _authenticate(manager)

    # The failure was handled — event dispatched, hook run, error parked —
    # but nothing answered it, so the run went on to the next authenticator.
    assert response is None
    token = storage.get_token()
    assert token is not None
    assert token.get_user_identifier() == "bob"


async def test_a_success_without_a_response_tries_the_next_authenticator() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager(
        [_Authenticator(identifier="alice"), _Authenticator(identifier="bob")],
        storage,
        RecordingDispatcher(),
        "api",
    )

    response = await _authenticate(manager)

    # Upstream behaviour: a success that answered nothing does not end the
    # run either — the next authenticator is still tried, and its token is
    # the one the storage ends up holding.
    assert response is None
    token = storage.get_token()
    assert token is not None
    assert token.get_user_identifier() == "bob"


async def test_a_required_badge_missing_is_answered_without_raising() -> None:
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager(
        [_Authenticator()],
        TokenStorage(),
        dispatcher,
        "api",
        required_badges=(PreAuthenticatedUserBadge,),
    )

    response = await _authenticate(manager)

    assert response is None
    failures = [event for event in dispatcher.events if isinstance(event, LoginFailureEvent)]
    assert len(failures) == 1
    assert isinstance(failures[0].get_exception(), BadCredentialsError)


async def test_a_missing_required_badge_error_names_every_missing_badge() -> None:
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager(
        [_Authenticator()],
        TokenStorage(),
        dispatcher,
        "api",
        required_badges=(PreAuthenticatedUserBadge, PasswordUpgradeBadge),
    )

    _ = await _authenticate(manager)

    failures = [event for event in dispatcher.events if isinstance(event, LoginFailureEvent)]
    reported = str(failures[0].get_exception())
    assert "PreAuthenticatedUserBadge" in reported
    assert "PasswordUpgradeBadge" in reported


async def test_a_sensitive_error_is_masked_when_hidden() -> None:
    @final
    class _UnknownUser(AbstractAuthenticator):
        @override
        def supports(self, request: ServerRequestInterface) -> bool | None:
            del request
            return True

        @override
        async def authenticate(self, request: ServerRequestInterface) -> Passport:
            del request

            def loader(identifier: str) -> InMemoryUser:
                raise UserNotFoundError(user_identifier=identifier)

            return Passport(UserBadge("ghost", user_loader=loader))

    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager(
        [_UnknownUser()],
        TokenStorage(),
        dispatcher,
        "api",
        expose_security_errors=ExposeSecurityLevel.NONE,
    )

    _ = await _authenticate(manager)

    failures = [event for event in dispatcher.events if isinstance(event, LoginFailureEvent)]
    assert len(failures) == 1
    assert isinstance(failures[0].get_exception(), BadCredentialsError)


async def test_no_authenticator_leaves_the_request_anonymous() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager([], storage, RecordingDispatcher(), "api")
    state = SecurityState()

    assert manager.supports(make_message(), state) is False
    assert await manager.authenticate_request(make_message(), state) is None
    assert storage.get_token() is None


def test_the_manager_logs_users_in_through_the_user_authenticator_interface() -> None:
    manager = AuthenticatorManager([], TokenStorage(), RecordingDispatcher(), "api")

    assert isinstance(manager, UserAuthenticatorInterface)


async def test_a_failure_handlers_answer_is_returned() -> None:
    response = ResponseFactory().create_response(401)

    @final
    class _Answering(AbstractAuthenticator):
        @override
        def supports(self, request: ServerRequestInterface) -> bool | None:
            del request
            return True

        @override
        async def authenticate(self, request: ServerRequestInterface) -> Passport:
            del request
            raise BadCredentialsError("no credential")

        @override
        async def on_authentication_failure(
            self,
            request: ServerRequestInterface,
            error: AuthenticationError,
        ) -> ResponseInterface | None:
            del request, error
            return response

    manager = AuthenticatorManager([_Answering()], TokenStorage(), RecordingDispatcher(), "api")

    assert await _authenticate(manager) is response


async def test_the_failure_event_is_dispatched_after_the_handler_ran() -> None:
    order: list[str] = []

    @final
    class _Recording(AbstractAuthenticator):
        @override
        def supports(self, request: ServerRequestInterface) -> bool | None:
            del request
            return True

        @override
        async def authenticate(self, request: ServerRequestInterface) -> Passport:
            del request
            raise BadCredentialsError("no credential")

        @override
        async def on_authentication_failure(
            self,
            request: ServerRequestInterface,
            error: AuthenticationError,
        ) -> ResponseInterface | None:
            del request, error
            order.append("handler")
            return None

    @final
    class _RecordingDispatcher:
        async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
            del event_name
            if isinstance(event, LoginFailureEvent):
                order.append("event")
            return event

    manager = AuthenticatorManager([_Recording()], TokenStorage(), _RecordingDispatcher(), "api")

    _ = await _authenticate(manager)

    assert order == ["handler", "event"]


async def test_a_login_failure_listener_answer_is_returned() -> None:
    response = ResponseFactory().create_response(401)

    @final
    class _AnsweringDispatcher:
        async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
            del event_name
            if isinstance(event, LoginFailureEvent):
                event.set_response(response)
            return event

    manager = AuthenticatorManager(
        [_BadTokenAuthenticator()], TokenStorage(), _AnsweringDispatcher(), "api"
    )

    assert await _authenticate(manager) is response


async def test_the_login_success_event_carries_the_token_the_storage_held() -> None:
    storage = TokenStorage()
    previous = NullToken()
    storage.set_token(previous)
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager([_Authenticator()], storage, dispatcher, "api")

    _ = await _authenticate(manager)

    successes = [event for event in dispatcher.events if isinstance(event, LoginSuccessEvent)]
    assert successes[0].get_previous_token() is previous


async def test_an_interactive_authenticator_announces_the_interactive_login() -> None:
    storage = TokenStorage()
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager([_InteractiveAuthenticator()], storage, dispatcher, "api")
    state = SecurityState()
    message = make_message()
    _ = manager.supports(message, state)

    _ = await manager.authenticate_request(message, state)

    announcements = [
        event for event in dispatcher.events if isinstance(event, InteractiveLoginEvent)
    ]
    assert len(announcements) == 1
    assert announcements[0].get_request() is message
    assert announcements[0].get_authenticated_token() is storage.get_token()


async def test_the_interactive_login_is_announced_under_its_name() -> None:
    @final
    class _NamingDispatcher:
        def __init__(self) -> None:
            self.dispatched: list[tuple[object, str | type | None]] = []

        async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
            self.dispatched.append((event, event_name))
            return event

    dispatcher = _NamingDispatcher()
    manager = AuthenticatorManager([_InteractiveAuthenticator()], TokenStorage(), dispatcher, "api")

    _ = await _authenticate(manager)

    announced = [
        name for event, name in dispatcher.dispatched if isinstance(event, InteractiveLoginEvent)
    ]
    assert announced == [SecurityEvents.INTERACTIVE_LOGIN]


async def test_a_non_interactive_authenticator_does_not_announce_the_interactive_login() -> None:
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager(
        [_InteractiveAuthenticator(interactive=False)],
        TokenStorage(),
        dispatcher,
        "api",
    )

    _ = await _authenticate(manager)

    announcements = [
        event for event in dispatcher.events if isinstance(event, InteractiveLoginEvent)
    ]
    assert announcements == []


async def test_an_authenticator_without_the_interface_does_not_announce_the_interactive_login() -> (
    None
):
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager([_Authenticator()], TokenStorage(), dispatcher, "api")

    _ = await _authenticate(manager)

    announcements = [
        event for event in dispatcher.events if isinstance(event, InteractiveLoginEvent)
    ]
    assert announcements == []


async def test_the_interactive_login_is_announced_between_handler_and_login_success() -> None:
    order: list[str] = []

    @final
    class _Recording(AbstractAuthenticator):
        @override
        def supports(self, request: ServerRequestInterface) -> bool | None:
            del request
            return True

        @override
        async def authenticate(self, request: ServerRequestInterface) -> Passport:
            del request
            return Passport(
                UserBadge("alice", user_loader=loader(roles=("ROLE_USER",))),
            )

        def is_interactive(self) -> bool:
            return True

        @override
        async def on_authentication_success(
            self,
            request: ServerRequestInterface,
            token: TokenInterface,
            firewall_name: str,
        ) -> ResponseInterface | None:
            del request, token, firewall_name
            order.append("handler")
            return None

    @final
    class _RecordingDispatcher:
        async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
            del event_name
            if isinstance(event, InteractiveLoginEvent):
                order.append("interactive")
            if isinstance(event, LoginSuccessEvent):
                order.append("success")
            return event

    manager = AuthenticatorManager([_Recording()], TokenStorage(), _RecordingDispatcher(), "api")

    _ = await _authenticate(manager)

    assert order == ["handler", "interactive", "success"]


async def test_authenticate_user_logs_a_known_user_in() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager([_Authenticator()], storage, RecordingDispatcher(), "api")
    user = InMemoryUser("alice", roles=["ROLE_USER"])

    response = await manager.authenticate_user(user, _Authenticator(), make_message())

    assert response is None
    token = storage.get_token()
    assert token is not None
    assert token.get_user_identifier() == "alice"


async def test_authenticate_user_skips_the_passport_check_and_the_success_event() -> None:
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager(
        [_Authenticator()],
        TokenStorage(),
        dispatcher,
        "api",
        required_badges=(PreAuthenticatedUserBadge,),
    )
    user = InMemoryUser("alice", roles=["ROLE_USER"])

    _ = await manager.authenticate_user(user, _Authenticator(), make_message())

    kinds = [type(event) for event in dispatcher.events]
    assert CheckPassportEvent not in kinds
    assert AuthenticationSuccessEvent not in kinds
    assert LoginSuccessEvent in kinds


async def test_authenticate_user_carries_the_badges_and_attributes_as_given() -> None:
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager([_Authenticator()], TokenStorage(), dispatcher, "api")
    user = InMemoryUser("alice", roles=["ROLE_USER"])
    badge = PasswordCredentials("secret")

    _ = await manager.authenticate_user(
        user,
        _Authenticator(),
        make_message(),
        badges=(badge,),
        attributes={"tenant": "acme"},
    )

    successes = [event for event in dispatcher.events if isinstance(event, LoginSuccessEvent)]
    passport = successes[0].get_passport()
    assert passport.has_badge(PasswordCredentials)
    assert passport.get_attribute("tenant") == "acme"
