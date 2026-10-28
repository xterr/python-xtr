"""The listener that checks the forgery token a passport's badge carries."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_security_csrf.csrf_token import CsrfToken
from xtr_security_csrf.csrf_token_manager_interface import (  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
    CsrfTokenManagerInterface,
)

from xtr_security_http.authenticator.passport.badge.csrf_token_badge import CsrfTokenBadge
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.exception.invalid_csrf_token_error import InvalidCsrfTokenError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents

__all__ = ["PRIORITY", "CsrfProtectionListener"]

#: The priority the token check runs at — beside the listener that resolves
#: an unknown user, ahead of the account pre-check
#: (:data:`~xtr_security_http.event_listener.user_checker_listener.PRE_PRIORITY`,
#: 256) and the credentials check
#: (:data:`~xtr_security_http.event_listener.check_credentials_listener.PRIORITY`,
#: 128). Two listeners share this priority, and the dispatcher runs same-priority
#: listeners in the order they were registered: this one must be registered
#: before the credentials listener, so a forged request is refused before any
#: user is loaded — the resolve step's dummy burn exists to equalise the cost
#: of an unknown user against a wrong password, and a request that never got
#: past the forgery check has no user timing to equalise.
PRIORITY = 512


@final
class CsrfProtectionListener(EventSubscriberInterface):
    """Checks the forgery token a passport's badge carries, on the passport check.

    An authenticator whose form carries a forgery token adds a
    :class:`~xtr_security_http.authenticator.passport.badge.csrf_token_badge.CsrfTokenBadge`
    naming the token's id and the value the request presented. This listener
    hands the pair to the token manager, which compares the value with what
    it stored when the page was rendered; a token the manager vouches for
    settles the badge, and one it does not fails the login with
    :class:`~xtr_security_http.exception.invalid_csrf_token_error.InvalidCsrfTokenError`
    — an authentication failure the manager's failure machinery answers, never
    a missing credential.

    The badge is all the listener reads: the authenticator already read the
    request when it built the passport, so the presented value travels on the
    badge and the listener needs nothing else from the event. A passport with
    no badge — an authenticator whose form carries no token — is left alone,
    and so is a badge another listener already settled.

    Until the badge is settled it reports unresolved, and the passport check
    fails on it: a request that skipped this listener cannot authenticate
    through a form whose token was never checked.
    """

    __slots__ = ("_csrf_token_manager",)

    def __init__(self, csrf_token_manager: CsrfTokenManagerInterface) -> None:
        """Record the manager that vouches for the values tokens are checked against.

        Args:
            csrf_token_manager: Compares a presented token value with the
                value stored under its id.
        """
        self._csrf_token_manager = csrf_token_manager

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to the passport check, ahead of the account and credentials checks."""
        return {CheckPassportEvent: ("check_passport", PRIORITY)}

    async def check_passport(self, event: CheckPassportEvent) -> None:
        """Vouch for the token the badge carries, then settle the badge.

        Raises:
            InvalidCsrfTokenError: When the request presented no value, or
                one the manager does not vouch for.
        """
        passport = event.get_passport()
        badge = passport.get_badge(CsrfTokenBadge)
        if badge is None or badge.is_resolved():
            return
        presented = badge.get_csrf_token()
        if not await self._csrf_token_manager.is_token_valid(
            CsrfToken(badge.get_csrf_token_id(), "" if presented is None else presented),
        ):
            raise InvalidCsrfTokenError("Invalid CSRF token.")
        badge.mark_resolved()
