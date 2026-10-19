"""The logout listener that answers a logout nothing else answered."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface

from xtr_security_http.event.logout_event import LogoutEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents

    from xtr_security_http.http_utils import HttpUtils

__all__ = ["DefaultLogoutListener"]


@final
class DefaultLogoutListener(EventSubscriberInterface):
    """Answers a logout with a redirect, when no listener answered it first.

    A logout needs an answer — the request asked for one — and the listeners
    before this one are the ones that may give it their own: a farewell page,
    a JSON body, a redirect of the application's choosing. This listener is
    the last word: a logout they left unanswered is answered with a redirect
    to the configured target, so the caller lands somewhere rather than in
    the void a request that changed nothing would.

    Runs ahead of the listeners that only clear — the session, the cookies,
    the stored tokens — so they still run after a logout this one answered,
    and behind the ones that answer with something of their own.
    """

    __slots__ = ("_http_utils", "_target_url")

    def __init__(self, http_utils: HttpUtils, target_url: str = "/") -> None:
        """Record where an unanswered logout redirects to.

        Args:
            http_utils: Builds the redirect, and guards its target against
                the configured domain rules.
            target_url: Where an unanswered logout redirects to — the home
                path by default.
        """
        self._http_utils = http_utils
        self._target_url = target_url

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a logout, after the listeners that answer it their own way."""
        return {LogoutEvent: ("on_logout", 64)}

    async def on_logout(self, event: LogoutEvent) -> None:
        """Redirect to the target, unless a listener before this one answered.

        The first response wins: a listener that answered the logout before
        this one decided where the caller lands, and this one leaves it
        alone.
        """
        if event.get_response() is not None:
            return
        event.set_response(
            self._http_utils.create_redirect_response(event.get_request(), self._target_url),
        )
