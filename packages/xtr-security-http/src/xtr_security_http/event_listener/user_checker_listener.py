"""The listener that runs the account checks around authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.user.user_interface import UserInterface

from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_security_core.user.user_checker_interface import UserCheckerInterface

__all__ = ["UserCheckerListener"]

#: The priority the pre-authentication check runs at on the passport check.
PRE_PRIORITY = 256

#: The priority the post-authentication check runs at on the success event.
POST_PRIORITY = 256


@final
class UserCheckerListener(EventSubscriberInterface):
    """Gates a user's own state, before credentials are checked and again after.

    Before the credentials check, on the passport check, it loads the user and
    runs the pre-authentication check — the account must not be disabled or
    locked to go on — unless the passport states the user was pre-authenticated
    elsewhere, an authentication that already vouched for the account. After a
    token is settled, on the success event, it runs the post-authentication
    check against the user the token carries, when that user is a user at all.
    """

    __slots__ = ("_user_checker",)

    def __init__(self, user_checker: UserCheckerInterface) -> None:
        """Record the checker the account state is gated by."""
        self._user_checker = user_checker

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Check pre-auth on the passport check, post-auth on the success event."""
        return {
            CheckPassportEvent: ("pre_check_credentials", PRE_PRIORITY),
            AuthenticationSuccessEvent: ("post_check_credentials", POST_PRIORITY),
        }

    async def pre_check_credentials(self, event: CheckPassportEvent) -> None:
        """Load the user and run the pre-authentication account check.

        A passport carrying a ``PreAuthenticatedUserBadge`` is skipped: the
        user was authenticated before the passport was built, and that
        authentication already vouched for the account's state.
        """
        passport = event.get_passport()
        if passport.has_badge(PreAuthenticatedUserBadge):
            return
        user = await passport.get_user()
        await self._user_checker.check_pre_auth(user)

    async def post_check_credentials(self, event: AuthenticationSuccessEvent) -> None:
        """Run the post-authentication account check against the token's user.

        A token whose user is not a ``UserInterface`` — an anonymous or a
        stringly-typed one — has no account state to check.
        """
        token = event.get_authentication_token()
        user = token.get_user()
        if isinstance(user, UserInterface):
            await self._user_checker.check_post_auth(user, token)
