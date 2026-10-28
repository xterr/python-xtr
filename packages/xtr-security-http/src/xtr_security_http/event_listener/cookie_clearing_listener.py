"""The logout listener that clears the cookies a logout should drop."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_foundation import cleared_cookie_header_value

from xtr_security_http.event.logout_event import LogoutEvent

from .cleared_cookie import (
    ClearedCookie,  # noqa: TC001 -- the container reads this constructor parameter's type at runtime
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents

__all__ = ["CookieClearingListener"]

_SET_COOKIE: str = "Set-Cookie"
"""The header that carries a cookie to a browser, set or cleared."""


@final
class CookieClearingListener(EventSubscriberInterface):
    """Answers a logout with the headers that clear the configured cookies.

    A logout should drop the cookies the site kept for the caller's
    convenience — a remember-me, a preference, a tracking id — and the ones
    configured here are cleared on the response the logout was answered with:
    a ``Set-Cookie`` header dated behind now for each, so the browser drops
    it at once. The path and the domain each cookie was set with are the
    ones the clearing header repeats, because a browser tells its cookies
    apart by all three.

    Runs last of the logout's listeners — after the default logout listener
    answered the request, so there is a response to clear the cookies on,
    and after the listeners that might still read one.
    """

    __slots__ = ("_cookies",)

    def __init__(self, cookies: Mapping[str, ClearedCookie]) -> None:
        """Record the cookies a logout of this firewall clears.

        Args:
            cookies: Each cookie to clear, mapped to the attributes it was
                set with — the path and the domain the clearing header must
                repeat, the secure flag and the cross-site rule it was set
                under.
        """
        self._cookies = dict(cookies)

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a logout, after every listener that answers or reads it."""
        return {LogoutEvent: ("on_logout", -255)}

    async def on_logout(self, event: LogoutEvent) -> None:
        """Clear the configured cookies on the response the logout was answered with.

        A logout no listener answered carries no response, and there is
        nothing to clear the cookies on; the headers the response already
        carries are kept, the clearing ones added beside them.
        """
        response = event.get_response()
        if response is None:
            return
        clearing = [
            cleared_cookie_header_value(
                name,
                path=cookie.path,
                domain=cookie.domain,
                secure=cookie.secure,
                samesite=cookie.samesite,
            )
            for name, cookie in self._cookies.items()
        ]
        if not clearing:
            return
        event.set_response(
            response.with_header(_SET_COOKIE, [*response.get_header(_SET_COOKIE), *clearing]),
        )
