"""The authenticator manager runs the fixed authentication sequence."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.exception import BadCredentialsError, UserNotFoundError

from tests.support.dispatchers import RecordingDispatcher
from tests.support.requests import make_request
from tests.support.users import loader
from xtr_security_http.authentication.authenticator_manager import AuthenticatorManager
from xtr_security_http.authentication.expose_security_level import ExposeSecurityLevel
from xtr_security_http.authenticator.abstract_authenticator import AbstractAuthenticator
from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.exception import InvalidAccessTokenError

if TYPE_CHECKING:
    from starlette.requests import Request
    from xtr_security_core.user.in_memory_user import InMemoryUser

pytestmark = pytest.mark.anyio


@final
class _Authenticator(AbstractAuthenticator):
    def __init__(self, *, supports: bool | None = True, identifier: str = "alice") -> None:
        self._supports = supports
        self._identifier = identifier

    @override
    def supports(self, request: Request) -> bool | None:
        del request
        return self._supports

    @override
    async def authenticate(self, request: Request) -> Passport:
        del request
        return Passport(
            UserBadge(self._identifier, user_loader=loader(roles=("ROLE_USER",))),
        )


@final
class _NoTokenAuthenticator(AbstractAuthenticator):
    @override
    def supports(self, request: Request) -> bool | None:
        del request
        return None

    @override
    async def authenticate(self, request: Request) -> Passport:
        del request
        raise BadCredentialsError("no token")


@final
class _BadTokenAuthenticator(AbstractAuthenticator):
    @override
    def supports(self, request: Request) -> bool | None:
        del request
        return None

    @override
    async def authenticate(self, request: Request) -> Passport:
        del request
        raise InvalidAccessTokenError


async def test_a_successful_authentication_stores_the_token() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager([_Authenticator()], storage, RecordingDispatcher(), "api")

    response = await manager.authenticate_request(make_request())

    assert response is None
    token = storage.get_token()
    assert token is not None
    assert token.get_user_identifier() == "alice"


async def test_the_check_passport_and_success_events_are_dispatched() -> None:
    dispatcher = RecordingDispatcher()
    manager = AuthenticatorManager([_Authenticator()], TokenStorage(), dispatcher, "api")

    _ = await manager.authenticate_request(make_request())

    kinds = [type(event) for event in dispatcher.events]
    assert CheckPassportEvent in kinds
    assert AuthenticationSuccessEvent in kinds


async def test_supports_reports_true_none_or_false() -> None:
    storage = TokenStorage()
    dispatcher = RecordingDispatcher()
    eager = AuthenticatorManager([_Authenticator(supports=True)], storage, dispatcher, "api")
    lazy = AuthenticatorManager([_Authenticator(supports=None)], storage, dispatcher, "api")
    none = AuthenticatorManager([_Authenticator(supports=False)], storage, dispatcher, "api")

    assert eager.supports(make_request()) is True
    assert lazy.supports(make_request()) is None
    assert none.supports(make_request()) is False


async def test_a_lazy_no_token_authenticator_abstains() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager([_NoTokenAuthenticator()], storage, RecordingDispatcher(), "api")

    response = await manager.authenticate_request(make_request())

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
        _ = await manager.authenticate_request(make_request())


async def test_a_false_authenticator_is_skipped() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager(
        [_Authenticator(supports=False), _Authenticator(identifier="bob")],
        storage,
        RecordingDispatcher(),
        "api",
    )

    _ = await manager.authenticate_request(make_request())

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
        _ = await manager.authenticate_request(make_request())


async def test_a_sensitive_error_is_masked_when_hidden() -> None:
    @final
    class _UnknownUser(AbstractAuthenticator):
        @override
        def supports(self, request: Request) -> bool | None:
            del request
            return True

        @override
        async def authenticate(self, request: Request) -> Passport:
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
        _ = await manager.authenticate_request(make_request())


async def test_no_authenticator_leaves_the_request_anonymous() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager([], storage, RecordingDispatcher(), "api")

    assert await manager.authenticate_request(make_request()) is None
    assert storage.get_token() is None
