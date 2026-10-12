"""What this deployment answers, and what it records, as tokens are issued.

Two of the seams an application plugs into: the one event that ever sees a
resource owner's own credentials, and the announcement that a token went out.
Both are registered the ordinary way — a decorator on a function the container
scans — so what the tests drive is what an application would write.
"""

from __future__ import annotations

from typing import Final

from xtr_event_dispatcher import as_event_listener
from xtr_security_core.user.in_memory_user import InMemoryUser

# The dispatcher reads a listener's annotations at runtime to find the event it
# hears, so neither of these can hide under TYPE_CHECKING.
from xtr_security_oauth2_server.event.user_resolve_event import UserResolveEvent
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.request_access_token_event import RequestAccessTokenEvent
from xtr_security_oauth2_server.request_event import RequestEvent

from .config import USER_IDENTIFIER, USER_PASSWORD, USER_ROLES

__all__ = ["ISSUED", "record_issued_token", "resolve_user"]

#: Every announcement this deployment heard that a token was issued. A test
#: clears it before driving a flow and reads it afterwards, which is how it
#: proves an application's own listener is reached.
ISSUED: Final[list[str]] = []


@as_event_listener(OAuth2Events.USER_RESOLVE)
async def resolve_user(event: UserResolveEvent) -> None:
    """Check the credentials the request carried, and say who they belong to.

    Leaving the user unresolved is what refuses the request, and it refuses it
    without saying which half was wrong.
    """
    if event.get_username() != USER_IDENTIFIER or event.get_password() != USER_PASSWORD:
        return
    _ = event.set_user(InMemoryUser(USER_IDENTIFIER, roles=list(USER_ROLES)))


@as_event_listener(RequestEvent.ACCESS_TOKEN_ISSUED)
async def record_issued_token(event: RequestAccessTokenEvent) -> None:
    """Record that a token went out, the way an audit listener would."""
    ISSUED.append(event.get_name())
