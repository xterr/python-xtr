"""The listener that throttles a login's attempts.

Every attempt is counted at the passport check, before its password is: a
check that only looked ahead would let a burst of concurrent attempts all
through before the first failure was counted. A successful login forgets
the account's count, over a limiter that builds its own keys.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import SystemClock
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_rate_limiter import RateLimit, RateLimitExceededEvent
from xtr_security_core.exception import (
    InvalidArgumentError,
    TooManyLoginAttemptsAuthenticationError,
)

from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher import SubscribedEvents
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_foundation import RequestRateLimiterInterface

__all__ = ["PRIORITY", "LoginThrottlingListener"]

#: The priority the throttling check runs at — before every other passport
#: check. What it must beat is the provider listener's loader setup (2048):
#: the throttling check reads the badge's identifier only, so it runs with
#: no loader in place, and running first means an attempt already over the
#: limit is refused before any other check spends anything on it — a user
#: load, a password verify — on a request that was never going to be
#: allowed through.
PRIORITY: Final = 2080


@final
class LoginThrottlingListener(EventSubscriberInterface):
    """Throttles the login attempts a request carries, through one request limiter.

    On the passport check the attempt is counted, so concurrent attempts
    past the limit are refused before any password is checked; a failed
    login counts nothing more. A successful one forgets the account's count
    — the local one only, the limiter's own asymmetry. A refused attempt is
    turned away with the core too-many-attempts error, carrying the minutes
    the caller must wait, and announced as an exceeded rate limit on the
    dispatcher the listener was given.
    """

    __slots__ = ("_clock", "_dispatcher", "_limiter", "_limiter_name")

    def __init__(
        self,
        limiter: RequestRateLimiterInterface,
        limiter_name: str | None = None,
        dispatcher: EventDispatcherInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Record the limiter, its configured name, and the dispatcher to announce on.

        Args:
            limiter: The request limiter the attempts count under — one
                that builds its own keys, such as the
                :class:`~xtr_security_http.rate_limiter.DefaultLoginRateLimiter`.
            limiter_name: The configured limiter's name, for the exceeded
                event's readers; ``None`` when the limiter is not a named
                configuration.
            dispatcher: The dispatcher to announce an exceeded rate limit
                on, when the listener was given one; the firewall's own,
                where the rest of the flow announces.
            clock: The reader of the current instant, for turning a refused
                attempt's wait into minutes.
        """
        self._limiter = limiter
        self._limiter_name = limiter_name
        self._dispatcher = dispatcher
        self._clock = clock if clock is not None else SystemClock()

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Count the attempt on the passport check first of all; forget on success."""
        return {
            CheckPassportEvent: ("check_passport", PRIORITY),
            LoginSuccessEvent: "on_successful_login",
        }

    async def check_passport(self, event: CheckPassportEvent) -> None:
        """Count the attempt, and refuse it over the limit before any other check spends anything.

        The username the passport names is parked on the request's security
        state first — the limiter reads its keys from there, and the form
        that renders again reads the same.

        Raises:
            TooManyLoginAttemptsAuthenticationError: When the attempt is
                over the limit, carrying the minutes the caller must wait.
        """
        badge = event.get_passport().get_badge(UserBadge)
        if badge is None:
            return
        request = event.get_request()
        if request is None:
            raise InvalidArgumentError(
                "The passport check carries no request: the throttling listener reads "
                "the attempt's keys off the request the passport arrived with.",
            )
        attributes = security_state_of(state_bag_of(request)).attributes
        attributes[SecurityRequestAttributes.LAST_USERNAME] = badge.get_user_identifier()

        limit = await self._limiter.consume(request)
        if limit.is_accepted():
            return

        if self._dispatcher is not None:
            # The event carries a rate limit of its own: the limiter answers
            # through an interface, which a third-party limiter implements.
            rejected = RateLimit(
                limit.remaining_tokens,
                limit.retry_after,
                accepted=False,
                limit=limit.limit,
                reset_at=limit.reset_at,
            )
            _ = await self._dispatcher.dispatch(
                RateLimitExceededEvent(rejected, limiter_name=self._limiter_name),
            )

        wait = math.ceil((limit.retry_after.timestamp() - self._clock.now().timestamp()) / 60)
        raise TooManyLoginAttemptsAuthenticationError(wait)

    async def on_successful_login(self, event: LoginSuccessEvent) -> None:
        """Forget the account's count.

        The global count, over the address, survives the login: the
        limiter keeps that asymmetry itself.
        """
        await self._limiter.reset(event.get_request())
