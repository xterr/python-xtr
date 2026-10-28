"""The session a stateful firewall parks on the request's security state.

A stateful firewall's chain builds a session for the request it runs — the
context listener reattaching the request's token, the login's strategy rotating
the ID — and parks it on the request's security state, under one key, so every
later step of the same request reaches the same object. This is the reader the
steps that answer a request — a form login storing its error, a success
handler returning to a saved path — share, so they all say "the request's
session" the one way.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, cast

from xtr_http_foundation import Session

from xtr_security_http._security_state import security_state_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["parked_session_of"]


def parked_session_of(request: ServerRequestInterface) -> Session | None:
    """Return the session the request's security state carries, if it carries one.

    The parked session is how this stack says a request has one: the context
    listener builds it while reattaching the request's token and parks it on
    the request's security state, and every later step of the same request —
    the login's session strategy, a logout, a form login's error page —
    reaches the same object through here. A request whose state carries none
    is a stateless one, or one no stateful machinery ran for.
    """
    bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
    if not isinstance(bag, MutableMapping):
        return None
    session = security_state_of(cast("MutableMapping[str, object]", bag)).attributes.get(
        SecurityRequestAttributes.SESSION
    )
    return session if isinstance(session, Session) else None
