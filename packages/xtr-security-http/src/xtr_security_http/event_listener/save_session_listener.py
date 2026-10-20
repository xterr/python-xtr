"""The listener that writes the session a stateful request reattached back out.

Nothing else in this stack saves a session: the chain's steps write to the
session the context listener parked — a login's error, its rotated ID, the
token a successful login stores — and those writes live in memory until
something writes them through the storage. This listener is that pass: on
the response event it saves the parked session and stages the cookie that
carries its ID, and on the finish event it saves what a request that never
produced a response still wrote.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_foundation import Session
from xtr_http_kernel.event import FinishRequestEvent, ResponseEvent

from xtr_security_http._security_state import SecurityState, security_state_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents

__all__ = ["PRIORITY", "SaveSessionListener"]

_SET_COOKIE: Final = "Set-Cookie"
"""The header that carries a cookie to a browser, set or cleared."""

PRIORITY: Final = -1000
"""Where the save runs on the response event — below every other listener.

The context listener's response half stores the token at the default
priority; the save must run after it, or the token would reach the storage
one request late. A priority nothing else claims keeps the two from having
to be ordered by hand.
"""


@final
class SaveSessionListener(EventSubscriberInterface):
    """Saves the session a stateful request reattached, and stages its cookie.

    The session is the one the request's security state carries — the object
    the context listener built and every step of the request wrote to — so
    what the chain wrote between requests is what the storage holds. A
    session that was never started is left entirely alone: nothing was read
    from it and nothing written, so it saves nothing and mints no cookie —
    a request that never touched its session must not tell the client to
    carry one.

    The response half saves before the head leaves, so a storage that fails
    fails the request loudly rather than losing the session quietly, and
    stages the ID cookie the session says is due — a fresh session, or one
    a login rotated. The finish half runs on every path, so a request that
    failed without producing a response still keeps what it wrote; it
    skips the requests the response half already saved, and stages no
    cookie — by the finish there is no head left to carry one.
    """

    __slots__ = ()

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to the response, and to the finish that runs on every path."""
        return {
            ResponseEvent: ("on_kernel_response", PRIORITY),
            FinishRequestEvent: "on_kernel_finish_request",
        }

    async def on_kernel_response(self, event: ResponseEvent) -> None:
        """Save the parked session, then stage the cookie its ID asks for.

        Raises:
            SessionError: When the storage fails to write the session —
                before the head leaves, so the failure is the request's
                to answer, not a loss nobody hears.
        """
        state = security_state_of(event.state)
        session = _parked_session_of(state)
        if session is None:
            return
        await _save(state, session)
        staged = session.staged_set_cookie()
        if staged is not None:
            event.headers.append(_SET_COOKIE, staged)

    async def on_kernel_finish_request(self, event: FinishRequestEvent) -> None:
        """Save the parked session a request that never answered still wrote.

        The finish runs whether the request was answered or not; the response
        half has already saved the answered ones, and its mark is what keeps
        this from writing the same session twice.

        Raises:
            SessionError: When the storage fails to write the session.
        """
        state = security_state_of(event.state)
        if state.attributes.get(SecurityRequestAttributes.SESSION_SAVED):
            return
        session = _parked_session_of(state)
        if session is None:
            return
        await _save(state, session)


def _parked_session_of(state: SecurityState) -> Session | None:
    """Return the session the request's security state carries, if it carries one."""
    session = state.attributes.get(SecurityRequestAttributes.SESSION)
    if not isinstance(session, Session) or not session.is_started():
        return None
    return session


async def _save(state: SecurityState, session: Session) -> None:
    """Write ``session`` through its storage and mark the request as saved.

    The mark is set only once the storage has taken the session: a save that
    raised leaves the request unmarked, so the failure is heard and a later
    half — the finish, or the response of the error that answered the
    failure — tries again rather than believing the session kept.
    """
    await session.save()
    state.attributes[SecurityRequestAttributes.SESSION_SAVED] = True
