"""The listener that runs the account checks around authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent

from xtr_security_http.event.check_passport_event import CheckPassportEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_security_core.user.user_checker_interface import UserCheckerInterface

__all__ = ["UserCheckerListener"]

#: The priority the pre-authentication check runs at on the passport check.
PRE_PRIORITY = 256


@final
class UserCheckerListener(EventSubscriberInterface):
    """Gates a user's own state, before credentials are checked and again after.

    Before the credentials check, on the passport check, it loads the user and
    runs the pre-authentication check — the account must not be disabled or
    locked to go on. After a token is settled, on the success event, it runs
    the post-authentication check against the user the token carries.
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
            AuthenticationSuccessEvent: "post_check_credentials",
        }

    async def pre_check_credentials(self, event: CheckPassportEvent) -> None:
        """Load the user and run the pre-authentication account check."""
        user = await event.get_passport().get_user()
        await self._user_checker.check_pre_auth(user)

    async def post_check_credentials(self, event: AuthenticationSuccessEvent) -> None:
        """Run the post-authentication account check against the token's user."""
        token = event.get_authentication_token()
        user = token.get_user()
        if user is not None:
            await self._user_checker.check_post_auth(user, token)
