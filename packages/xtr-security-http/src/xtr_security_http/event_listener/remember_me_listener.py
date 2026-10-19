"""The listener that sets the remember-me cookie a login earned, and clears it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface

from xtr_security_http.authenticator.passport.badge.remember_me_badge import RememberMeBadge
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.event.token_deauthenticated_event import TokenDeauthenticatedEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_logging_contracts import LoggerInterface

    from xtr_security_http.remember_me.remember_me_handler_interface import (
        RememberMeHandlerInterface,
    )

__all__ = ["RememberMeListener"]


@final
class RememberMeListener(EventSubscriberInterface):
    """Answers a login's remember-me ask, and every ending that must drop the cookie.

    On a successful login, the cookie is set only when the badge was
    enabled — the conditions listener's doing — and any cookie the request
    still carries is cleared first, so a login as another user never leaves
    the previous one remembered. On a failed login, a logout and a
    deauthentication, the cookie is cleared: a login that did not happen
    must not remember one that did, and a session the refresh refused must
    not be re-established by what it left behind.
    """

    __slots__ = ("_logger", "_remember_me_handler")

    def __init__(
        self,
        remember_me_handler: RememberMeHandlerInterface,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record the handler that sets and clears the cookie, and the logger.

        Args:
            remember_me_handler: The one voice on what the cookie holds —
                every set and clear this listener asks for goes through it.
            logger: Where the decisions are logged, or ``None``.
        """
        self._remember_me_handler = remember_me_handler
        self._logger = logger

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a login's both outcomes, and to the endings that drop the cookie."""
        return {
            LoginSuccessEvent: ("on_login_success", -64),
            LoginFailureEvent: "clear_cookie",
            LogoutEvent: "clear_cookie",
            TokenDeauthenticatedEvent: "clear_cookie",
        }

    async def on_login_success(self, event: LoginSuccessEvent) -> None:
        """Set the cookie the login asked for, after clearing any it still carried.

        A passport without the badge is a login through an authenticator
        that never offered remembering, and nothing is touched. With the
        badge, any cookie the request still carries is cancelled first — a
        login must not leave the previous user remembered — and a badge
        that was never enabled, the conditions unmet, leaves it at that:
        cleared, and nothing new staged.
        """
        badge = event.get_passport().get_badge(RememberMeBadge)
        if badge is None:
            if self._logger is not None:
                self._logger.debug(
                    "Remember me skipped: your authenticator does not support it.",
                    {"authenticator": type(event.get_authenticator()).__name__},
                )
            return
        request = event.get_request()
        await self._remember_me_handler.clear_remember_me_cookie(request)
        if not badge.is_enabled():
            if self._logger is not None:
                self._logger.debug("Remember me skipped: the RememberMeBadge is not enabled.", {})
            return
        if self._logger is not None:
            self._logger.debug("Remember-me was requested; setting cookie.", {})
        await self._remember_me_handler.create_remember_me_cookie(request, event.get_user())

    async def clear_cookie(
        self,
        event: LoginFailureEvent | LogoutEvent | TokenDeauthenticatedEvent,
    ) -> None:
        """Clear the cookie on an ending that must not leave a login remembered."""
        await self._remember_me_handler.clear_remember_me_cookie(event.get_request())
