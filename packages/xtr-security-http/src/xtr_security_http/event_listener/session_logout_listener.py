"""The logout listener that invalidates the session a request reattached."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_foundation import Session

from xtr_security_http._security_state import security_state_of
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["SessionLogoutListener"]


@final
class SessionLogoutListener(EventSubscriberInterface):
    """Invalidates the session a logging-out request reattached.

    A session is what keeps a caller logged in across requests, so a logout
    ends it: the session is invalidated — its attributes dropped, its stored
    entry deleted, its ID re-issued — so the next request of the same
    browser reattaches a session that answers for nobody.

    The session is the one the request's security state carries — the one
    the context listener parked when the request reattached it, the same
    object the login's session strategy rotates. A logout of a request with
    no session — a stateless firewall, or a logout outside a stateful
    chain — has nothing to invalidate, and the listener leaves it at that.
    """

    __slots__ = ()

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a logout, beside the listeners that answer it."""
        return {LogoutEvent: "on_logout"}

    async def on_logout(self, event: LogoutEvent) -> None:
        """Invalidate the session the request's security state carries.

        The parked session is how this stack says a request has one: it is
        the one object the request's halves share, and the one whose
        invalidation ends the login the request is logging out.
        """
        session = self._session_of(event.get_request())
        if session is not None:
            await session.invalidate()

    @staticmethod
    def _session_of(request: ServerRequestInterface) -> Session | None:
        """Return the session parked on the request's security state, if any."""
        bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
        if not isinstance(bag, MutableMapping):
            return None
        session = security_state_of(cast("MutableMapping[str, object]", bag)).attributes.get(
            SecurityRequestAttributes.SESSION
        )
        return session if isinstance(session, Session) else None
