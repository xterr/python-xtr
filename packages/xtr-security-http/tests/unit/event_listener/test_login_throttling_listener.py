"""The throttling listener: count every attempt before its password is checked, forget on success.

The priorities are pinned too: the throttling check runs at 2080, above
the provider listener's loader setup (2048), the credentials check's
early user resolve (512), the account pre-check (256) and the
credentials check (128) — so an attempt already over the limit is
refused before any other check spends anything on it.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_rate_limiter import (
    InMemoryStorage,
    LimiterConfig,
    RateLimit,
    RateLimiterFactory,
    RateLimitExceededEvent,
)
from xtr_security_core.exception import (
    InvalidArgumentError,
    TooManyLoginAttemptsAuthenticationError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.dispatchers import RecordingDispatcher
from tests.support.http import FakeAccessTokenHandler
from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event_listener.check_credentials_listener import (
    PRIORITY as CREDENTIALS_PRIORITY,
)
from xtr_security_http.event_listener.check_credentials_listener import RESOLVE_PRIORITY
from xtr_security_http.event_listener.login_throttling_listener import (
    PRIORITY,
    LoginThrottlingListener,
)
from xtr_security_http.event_listener.user_checker_listener import PRE_PRIORITY
from xtr_security_http.event_listener.user_provider_listener import PRIORITY as PROVIDER_PRIORITY
from xtr_security_http.rate_limiter.default_login_rate_limiter import DefaultLoginRateLimiter
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

_BURST = 50
"""How many attempts arrive at once in the burst test."""

_LIMIT = 3
"""How many attempts an account is allowed in the burst test."""


@final
class _RecordingLimiter:
    """A limiter that can look ahead, recording every call and answering a set limit."""

    def __init__(self, limit: RateLimit) -> None:
        self._limit = limit
        self.peeks: list[object] = []
        self.consumes: list[object] = []
        self.resets: list[object] = []

    async def consume(self, request: ServerRequestInterface) -> RateLimit:
        self.consumes.append(request)
        return self._limit

    async def peek(self, request: ServerRequestInterface) -> RateLimit:
        self.peeks.append(request)
        return self._limit

    async def reset(self, request: ServerRequestInterface) -> None:
        self.resets.append(request)


def _authenticator() -> AccessTokenAuthenticator:
    return AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )


def _request(bag: dict[str, object]) -> ServerRequestInterface:
    """Return a request from one address, carrying the state bag ``bag``."""
    return make_message(client=("127.0.0.1", 80)).with_attribute(
        SecurityRequestAttributes.STATE_BAG, bag
    )


def _check_event(request: ServerRequestInterface) -> CheckPassportEvent:
    return CheckPassportEvent(_authenticator(), SelfValidatingPassport(UserBadge("alice")), request)


def _success_event(request: ServerRequestInterface) -> LoginSuccessEvent:
    return LoginSuccessEvent(
        _authenticator(),
        SelfValidatingPassport(UserBadge("alice")),
        PostAuthenticationToken(InMemoryUser("alice"), "api", ()),
        request,
        None,
        "api",
    )


def _granted(remaining: int = 3, full: int = 5) -> RateLimit:
    return RateLimit(remaining, datetime.now(UTC), accepted=True, limit=full)


def _refused(wait_minutes: int = 12) -> RateLimit:
    return RateLimit(
        0, datetime.now(UTC) + timedelta(minutes=wait_minutes), accepted=False, limit=5
    )


def test_the_throttling_check_runs_before_every_other_passport_check() -> None:
    assert PRIORITY == 2080
    assert PRIORITY > PROVIDER_PRIORITY  # 2048: the badge's loader setup.
    assert PRIORITY > RESOLVE_PRIORITY  # 512: the credentials check's early resolve.
    assert PRIORITY > PRE_PRIORITY  # 256: the account pre-check.
    assert PRIORITY > CREDENTIALS_PRIORITY  # 128: the credentials check.


async def test_the_check_counts_the_attempt_even_on_a_limiter_that_can_look_ahead() -> None:
    limiter = _RecordingLimiter(_granted(remaining=3, full=5))
    listener = LoginThrottlingListener(limiter)
    bag: dict[str, object] = {}

    await listener.check_passport(_check_event(_request(bag)))

    assert len(limiter.consumes) == 1
    assert len(limiter.peeks) == 0
    assert security_state_of(bag).attributes.get(SecurityRequestAttributes.LAST_USERNAME) == "alice"


async def test_concurrent_attempts_beyond_the_limit_are_refused_before_the_password_check() -> None:
    def factory(limit: int) -> RateLimiterFactory:
        config = LimiterConfig("fixed_window", limit=limit, interval="1 minute")
        return RateLimiterFactory(f"login-{limit}", config, InMemoryStorage())

    listener = LoginThrottlingListener(
        DefaultLoginRateLimiter(factory(_BURST * 2), factory(_LIMIT), "a-secret")
    )

    answers = await asyncio.gather(
        *(listener.check_passport(_check_event(_request({}))) for _ in range(_BURST)),
        return_exceptions=True,
    )

    passed = [answer for answer in answers if answer is None]
    assert len(passed) == _LIMIT
    assert all(
        isinstance(answer, TooManyLoginAttemptsAuthenticationError)
        for answer in answers
        if answer is not None
    )


async def test_it_refuses_an_over_the_limit_attempt_with_the_minutes_to_wait() -> None:
    limiter = _RecordingLimiter(_refused(wait_minutes=12))
    listener = LoginThrottlingListener(limiter)
    bag: dict[str, object] = {}

    with pytest.raises(TooManyLoginAttemptsAuthenticationError) as raised:
        await listener.check_passport(_check_event(_request(bag)))

    assert raised.value.threshold == 12


async def test_it_announces_the_refusal_as_an_exceeded_rate_limit() -> None:
    limiter = _RecordingLimiter(_refused(wait_minutes=12))
    dispatcher = RecordingDispatcher()
    listener = LoginThrottlingListener(limiter, "login", dispatcher)
    bag: dict[str, object] = {}

    with pytest.raises(TooManyLoginAttemptsAuthenticationError):
        await listener.check_passport(_check_event(_request(bag)))

    assert len(dispatcher.events) == 1
    event = dispatcher.events[0]
    assert isinstance(event, RateLimitExceededEvent)
    assert event.limiter_name == "login"
    assert not event.rate_limit.is_accepted()


async def test_a_failed_login_is_not_counted_a_second_time() -> None:
    assert LoginFailureEvent not in LoginThrottlingListener.get_subscribed_events()


async def test_a_successful_login_resets_the_local_count() -> None:
    limiter = _RecordingLimiter(_granted())
    listener = LoginThrottlingListener(limiter)
    bag: dict[str, object] = {}

    await listener.on_successful_login(_success_event(_request(bag)))

    assert len(limiter.resets) == 1


async def test_it_refuses_a_passport_check_that_carries_no_request() -> None:
    limiter = _RecordingLimiter(_granted())
    listener = LoginThrottlingListener(limiter)

    with pytest.raises(InvalidArgumentError):
        await listener.check_passport(
            CheckPassportEvent(_authenticator(), SelfValidatingPassport(UserBadge("alice")))
        )
