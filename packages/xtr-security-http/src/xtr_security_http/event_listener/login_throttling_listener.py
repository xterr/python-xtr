"""The listener that throttles a login's failed attempts.

Most requests pass; only the failures should count. So the passport check
looks ahead without spending anything, a failed login spends one attempt,
and a successful one forgets the account's count — the shape that keeps
the counting to one trip per outcome, over a limiter that builds its own
keys.
"""

from __future__ import annotations

import math
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override
from xtr_clock import SystemClock
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_foundation import PeekableRequestRateLimiterInterface
from xtr_rate_limiter import RateLimit, RateLimitExceededEvent
from xtr_security_core.exception import (
    InvalidArgumentError,
    TooManyLoginAttemptsAuthenticationError,
)

from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_failure_event import LoginFailureEvent
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

    On the passport check the attempt is looked ahead at, not counted: most
    attempts pass, and only the failures should spend anything. A failed
    login counts one attempt; a successful one forgets the account's count —
    the local one only, the limiter's own asymmetry. An attempt the look
    ahead refuses is turned away with the core too-many-attempts error,
    carrying the minutes the caller must wait, and announced as an exceeded
    rate limit on the dispatcher the listener was given.
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
        """Throttle the passport check first of all; count a failure; forget on success."""
        return {
            CheckPassportEvent: ("check_passport", PRIORITY),
            LoginFailureEvent: "on_failed_login",
            LoginSuccessEvent: "on_successful_login",
        }

    async def check_passport(self, event: CheckPassportEvent) -> None:
        """Refuse an attempt already over the limit, before any other check spends anything.

        The username the passport names is parked on the request's security
        state first — the limiter reads its keys from there, and the form
        that renders again reads the same. A limiter that can look ahead is
        looked ahead at: a window with a token left is passed with nothing
        spent, and remembered as untouched when it was full, so a successful
        login has nothing to forget. A limiter that cannot is counted here
        instead, and a successful login still forgets its count.

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

        if isinstance(self._limiter, PeekableRequestRateLimiterInterface):
            limit = await self._limiter.peek(request)
            # A look ahead spends nothing, so it is accepted even with no
            # token left; both are read, for a third-party limiter that
            # counts a look ahead anyway.
            if limit.is_accepted() and limit.remaining_tokens != 0:
                attributes[SecurityRequestAttributes.LOGIN_THROTTLING_UNTOUCHED] = (
                    limit.remaining_tokens == limit.limit
                )
                return
        else:
            limit = await self._limiter.consume(request)
            if limit.is_accepted():
                return

        if self._dispatcher is not None:
            # The event carries the limit's state, not the limiter's own
            # answer object: a look ahead that found no token left is
            # accepted, and an exceeded event reports a refusal.
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

    async def on_failed_login(self, event: LoginFailureEvent) -> None:
        """Count the failed attempt, when the limiter left it to be counted here.

        A limiter that can look ahead spent nothing on the passport check,
        so the failure is where the attempt is counted. A limiter that
        cannot counted it there already.
        """
        if isinstance(self._limiter, PeekableRequestRateLimiterInterface):
            _ = await self._limiter.consume(event.get_request())

    async def on_successful_login(self, event: LoginSuccessEvent) -> None:
        """Forget the account's count, unless the window was never touched.

        A window that was full when the passport was checked has nothing a
        successful login needs to forget — and the global count, over the
        address, must survive the login besides; the limiter keeps that
        asymmetry itself.
        """
        request = event.get_request()
        if isinstance(self._limiter, PeekableRequestRateLimiterInterface):
            bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
            if isinstance(bag, MutableMapping) and security_state_of(
                cast("MutableMapping[str, object]", bag)
            ).attributes.get(SecurityRequestAttributes.LOGIN_THROTTLING_UNTOUCHED):
                return

        await self._limiter.reset(request)
