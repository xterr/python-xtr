"""The authenticator manager runs the fixed authentication sequence."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.exception import (
    BadCredentialsError,
    InvalidArgumentError,
    UserNotFoundError,
)

from tests.support.dispatchers import RecordingDispatcher
from tests.support.messages import make_message
from tests.support.users import loader
from xtr_security_http._security_state import SecurityState
from xtr_security_http.authentication.authenticator_manager import AuthenticatorManager
from xtr_security_http.authentication.expose_security_level import ExposeSecurityLevel
from xtr_security_http.authenticator.abstract_authenticator import AbstractAuthenticator
from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.exception import InvalidAccessTokenError
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.user.in_memory_user import InMemoryUser

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface

pytestmark = pytest.mark.anyio


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


async def test_a_bad_token_propagates() -> None:
    manager = AuthenticatorManager(
        [_BadTokenAuthenticator()],
        TokenStorage(),
        RecordingDispatcher(),
        "api",
    )

    with pytest.raises(InvalidAccessTokenError):
        _ = await _authenticate(manager)


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


async def test_a_required_badge_missing_is_bad_credentials() -> None:
    manager = AuthenticatorManager(
        [_Authenticator()],
        TokenStorage(),
        RecordingDispatcher(),
        "api",
        required_badges=(PreAuthenticatedUserBadge,),
    )

    with pytest.raises(BadCredentialsError):
        _ = await _authenticate(manager)


async def test_a_missing_required_badge_error_names_every_missing_badge() -> None:
    manager = AuthenticatorManager(
        [_Authenticator()],
        TokenStorage(),
        RecordingDispatcher(),
        "api",
        required_badges=(PreAuthenticatedUserBadge, PasswordUpgradeBadge),
    )

    with pytest.raises(BadCredentialsError) as failure:
        _ = await _authenticate(manager)

    reported = str(failure.value)
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

    manager = AuthenticatorManager(
        [_UnknownUser()],
        TokenStorage(),
        RecordingDispatcher(),
        "api",
        expose_security_errors=ExposeSecurityLevel.NONE,
    )

    with pytest.raises(BadCredentialsError):
        _ = await _authenticate(manager)


async def test_no_authenticator_leaves_the_request_anonymous() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager([], storage, RecordingDispatcher(), "api")
    state = SecurityState()

    assert manager.supports(make_message(), state) is False
    assert await manager.authenticate_request(make_message(), state) is None
    assert storage.get_token() is None
