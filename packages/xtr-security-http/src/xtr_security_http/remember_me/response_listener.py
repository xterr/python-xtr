"""Moves a staged remember-me cookie onto the response about to leave."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_kernel.event.response_event import ResponseEvent

from xtr_security_http._security_state import security_state_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .remember_me_cookie import RememberMeCookie

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents

__all__ = ["ResponseListener"]

_SET_COOKIE = "Set-Cookie"
"""The header that carries a cookie to a browser, set or cleared."""


@final
class ResponseListener(EventSubscriberInterface):
    """Writes the remember-me cookie a handler staged onto the outgoing head.

    A handler sets or clears the cookie while the request is still being
    authenticated — before any response exists — so it stages the whole
    cookie on the request's security state, and this listener, on the
    lifecycle's response event, is the pass that moves it: the finished
    ``Set-Cookie`` value is appended to the headers that are about to leave,
    beside whatever the response already carries.

    A request whose state staged no cookie leaves the response untouched —
    most requests never present or earn one. This kernel has no sub-request
    mechanism, so every response event is the request's own; there is no
    main-request guard to keep, and none is kept.
    """

    __slots__ = ()

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to the response event, at the default priority."""
        return {ResponseEvent: "on_kernel_response"}

    async def on_kernel_response(self, event: ResponseEvent) -> None:
        """Append the staged cookie to the headers that are about to leave."""
        state = security_state_of(event.state)
        cookie = state.attributes.get(SecurityRequestAttributes.REMEMBER_ME_COOKIE)
        if not isinstance(cookie, RememberMeCookie):
            return
        event.headers.append(_SET_COOKIE, cookie.header_value())
