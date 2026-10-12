"""How this deployment establishes the resource owner the password flow names."""

from __future__ import annotations

from xtr_event_dispatcher import as_event_listener
from xtr_security_core.user.in_memory_user import InMemoryUser

# The dispatcher reads a listener's annotations at runtime to find the event it
# hears, so the event class cannot hide under TYPE_CHECKING.
from xtr_security_oauth2_server.event.user_resolve_event import UserResolveEvent
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

from .config import USER_IDENTIFIER, USER_PASSWORD, USER_ROLES

__all__ = ["resolve_user"]


@as_event_listener(OAuth2Events.USER_RESOLVE)
async def resolve_user(event: UserResolveEvent) -> None:
    """Check the credentials that establish the resource owner."""
    if event.get_username() != USER_IDENTIFIER or event.get_password() != USER_PASSWORD:
        return
    _ = event.set_user(InMemoryUser(USER_IDENTIFIER, roles=list(USER_ROLES)))
