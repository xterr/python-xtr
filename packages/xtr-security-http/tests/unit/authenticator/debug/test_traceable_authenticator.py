"""The traceable wrapper records what the wrapped authenticator did."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
)

from tests.support.messages import make_message
from tests.support.users import loader
from xtr_security_http.authenticator.abstract_authenticator import AbstractAuthenticator
from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
from xtr_security_http.authenticator.debug.traceable_authenticator import TraceableAuthenticator
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.interactive_authenticator_interface import (
    InteractiveAuthenticatorInterface,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http.authenticator.passport.passport import Passport

pytestmark = pytest.mark.anyio


@final
class _Explaining(AbstractAuthenticator):
    """Answers supports with a fixed value, explaining a negative one."""

    def __init__(self, *, supported: bool | None) -> None:
        self._supported = supported

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
        if isinstance(reasons, UnsupportedReasons):
            reasons.add("the request carries no bearer token")
        return self._supported

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        del request
        return SelfValidatingPassport(UserBadge("alice"))


@final
class _Answering(AbstractAuthenticator):
    """Answers a failure with a fixed response."""

    def __init__(self, response: ResponseInterface) -> None:
        self._response = response

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
        return self._response


def test_it_records_the_wrapped_supports_answer() -> None:
    for supported in (True, None, False):
        traceable = TraceableAuthenticator(_Explaining(supported=supported))

        assert traceable.supports(make_message()) is supported
        assert traceable.get_info()["supports"] is supported


def test_it_collects_the_reasons_the_wrapped_authenticator_explained() -> None:
    traceable = TraceableAuthenticator(_Explaining(supported=False))

    _ = traceable.supports(make_message())

    assert traceable.get_info()["unsupported_reasons"] == ("the request carries no bearer token",)


def test_the_reasons_attribute_rides_the_request_for_the_supports_call_alone() -> None:
    request = make_message()

    _ = TraceableAuthenticator(_Explaining(supported=False)).supports(request)

    assert request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS) is None


async def test_it_records_the_passport_and_how_long_it_took() -> None:
    traceable = TraceableAuthenticator(_Explaining(supported=True))
    _ = traceable.supports(make_message())

    passport = await traceable.authenticate(make_message())

    assert traceable.get_info()["passport"] is passport
    assert isinstance(traceable.get_info()["duration"], float)


async def test_it_records_the_outcome_of_both_hooks() -> None:
    traceable = TraceableAuthenticator(_Explaining(supported=True))
    error = BadCredentialsError()

    _ = await traceable.on_authentication_success(make_message(), NullToken(), "api")
    assert traceable.get_info()["authenticated"] is True

    _ = await traceable.on_authentication_failure(make_message(), error)
    assert traceable.get_info()["authenticated"] is False
    assert traceable.get_info()["exception"] is error


async def test_it_passes_the_token_creation_through() -> None:
    traceable = TraceableAuthenticator(_Explaining(supported=True))
    badge = UserBadge("alice", user_loader=loader())
    passport = SelfValidatingPassport(badge)
    _ = await badge.get_user()

    token = await traceable.create_token(passport, "api")

    assert token.get_user_identifier() == "alice"


async def test_a_response_from_the_wrapped_failure_handler_is_passed_through() -> None:
    response = ResponseFactory().create_response(401)
    traceable = TraceableAuthenticator(_Answering(response))

    answered = await traceable.on_authentication_failure(make_message(), BadCredentialsError())

    assert answered is response


def test_it_opens_to_the_wrapped_authenticator_and_satisfies_the_interface() -> None:
    inner = _Explaining(supported=True)
    traceable = TraceableAuthenticator(inner)

    assert isinstance(traceable, AuthenticatorInterface)
    assert traceable.get_authenticator() is inner


def test_it_delegates_the_interactive_announcement_to_the_wrapped_authenticator() -> None:
    @final
    class _Interactive(AbstractAuthenticator):
        """A wrapped authenticator that reports its logins as the user's own act."""

        def __init__(self, *, interactive: bool) -> None:
            super().__init__()
            self._interactive = interactive

        @override
        def supports(self, request: ServerRequestInterface) -> bool | None:
            """Answer yes; the test never reaches this."""
            del request
            return True

        @override
        async def authenticate(self, request: ServerRequestInterface) -> Passport:
            """Hand back a self-validating passport; the test never reaches this."""
            del request
            return SelfValidatingPassport(UserBadge("alice"))

        def is_interactive(self) -> bool:
            """Answer as the test built this authenticator to."""
            return self._interactive

    assert isinstance(
        TraceableAuthenticator(_Interactive(interactive=True)), InteractiveAuthenticatorInterface
    )
    assert TraceableAuthenticator(_Interactive(interactive=True)).is_interactive() is True
    assert TraceableAuthenticator(_Interactive(interactive=False)).is_interactive() is False


def test_a_wrapped_authenticator_without_the_interface_answers_not_interactive() -> None:
    traceable = TraceableAuthenticator(_Explaining(supported=True))

    assert traceable.is_interactive() is False
