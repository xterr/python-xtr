"""What this deployment answers when a resource owner is asked to approve.

The same stateless consent the redirect-flow deployment beside this one uses:
one listener checks the credential that establishes the resource owner, the
other approves outright. Neither knows the flow being approved belongs to an
add-on, which is the point — an add-on's grant reaches the deployment's own
consent through the same event the shipped grant does.
"""

from __future__ import annotations

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

__all__ = ["approve_authorization", "resolve_user"]


@as_event_listener(OAuth2Events.USER_RESOLVE)
async def resolve_user(event: UserResolveEvent) -> None:
    """Check the credentials that establish the resource owner."""
    if event.get_username() != USER_IDENTIFIER or event.get_password() != USER_PASSWORD:
        return
    _ = event.set_user(InMemoryUser(USER_IDENTIFIER, roles=list(USER_ROLES)))


@as_event_listener(OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE)
async def approve_authorization(event: AuthorizationRequestResolveEvent) -> None:
    """Approve the request, as a deployment whose consent was already given."""
    _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)
