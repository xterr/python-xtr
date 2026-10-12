"""What this deployment answers when a resource owner is asked to approve.

Consent is stateless: nothing is remembered between the two halves of the
flow, so a listener either resolves the request or answers the browser itself.
This one approves outright, which stands for a deployment whose consent was
already given — the shape a test can drive without a form.
"""

from __future__ import annotations

from typing import Final

from xtr_event_dispatcher import as_event_listener
from xtr_security_core.user.in_memory_user import InMemoryUser

# The dispatcher reads a listener's annotations at runtime to find the event it
# hears, so neither event class can hide under TYPE_CHECKING.
from xtr_security_oauth2_server.event.authorization_request_resolve_event import (
    AuthorizationRequestResolveEvent,
)
from xtr_security_oauth2_server.event.user_resolve_event import UserResolveEvent
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

from .config import USER_IDENTIFIER, USER_PASSWORD, USER_ROLES

__all__ = ["ASKED", "approve_authorization", "resolve_user"]

#: Every client this deployment was asked to approve, in order. A test clears
#: it before driving the flow, which is how it proves the consent event is the
#: one place the decision is made.
ASKED: Final[list[str]] = []


@as_event_listener(OAuth2Events.USER_RESOLVE)
async def resolve_user(event: UserResolveEvent) -> None:
    """Check the credentials that establish the resource owner."""
    if event.get_username() != USER_IDENTIFIER or event.get_password() != USER_PASSWORD:
        return
    _ = event.set_user(InMemoryUser(USER_IDENTIFIER, roles=list(USER_ROLES)))


@as_event_listener(OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE)
async def approve_authorization(event: AuthorizationRequestResolveEvent) -> None:
    """Approve the request, recording which client was asked about.

    A request is denied until something approves it, so this is the whole of
    what makes the flow complete.
    """
    ASKED.append(event.get_client().get_identifier())
    _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)
