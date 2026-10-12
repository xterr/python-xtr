"""What this deployment answers when a resource owner is asked to approve.

The consent page and the approval are two passes of the same endpoint, because
nothing is remembered between them: the first pass answers the browser itself,
the form posts the original query back with a marker of its own, and the second
pass is approved.

The marker here rides on the ``state``, which is the one thing the event
carries that the form controls. A real deployment reads a field of its own off
the request; what is being exercised is the endpoint's two branches, not how a
form is shaped.
"""

from __future__ import annotations

from typing import Final

from xtr_event_dispatcher import as_event_listener
from xtr_http_kernel.bridge import Response
from xtr_security_core.user.in_memory_user import InMemoryUser

# The dispatcher reads a listener's annotations at runtime to find the event it
# hears, so neither event class can hide under TYPE_CHECKING.
from xtr_security_oauth2_server.event.authorization_request_resolve_event import (
    AuthorizationRequestResolveEvent,
)
from xtr_security_oauth2_server.event.user_resolve_event import UserResolveEvent
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

from .config import USER_IDENTIFIER, USER_PASSWORD, USER_ROLES

__all__ = ["CONSENT_PAGE", "GRANTED", "ask_for_consent", "resolve_user"]

GRANTED: Final = "the-form-posted-back"
"""The state the consent form posts back with, standing for "they said yes"."""

CONSENT_PAGE: Final = "<form>Allow this client?</form>"
"""What the browser is shown on the first pass."""


@as_event_listener(OAuth2Events.USER_RESOLVE)
async def resolve_user(event: UserResolveEvent) -> None:
    """Check the credentials that establish the resource owner."""
    if event.get_username() != USER_IDENTIFIER or event.get_password() != USER_PASSWORD:
        return
    _ = event.set_user(InMemoryUser(USER_IDENTIFIER, roles=list(USER_ROLES)))


@as_event_listener(OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE)
async def ask_for_consent(event: AuthorizationRequestResolveEvent) -> None:
    """Show the consent page, or approve the request the form posted back."""
    if event.get_state() == GRANTED:
        _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)

        return
    page = Response(200).with_header("content-type", "text/html")
    _ = page.get_body().write(CONSENT_PAGE.encode())
    _ = event.set_response(page)
