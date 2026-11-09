"""What this deployment answers when a resource owner signs in and is asked to approve.

One listener checks the credential that establishes the resource owner, the
other answers the consent question the way this package's README has an
application answer it. Its consent was already given for the client every
sign-in here is driven as, and never given for ``CONSENT_CLIENT_ID``: a
sign-in as that one is refused when the request forbids showing a page, and
shown the page otherwise.

Neither listener knows an OpenID Connect provider is listed: the provider's
flow reaches them through the same events the shipped flow does, and what the
client asked of the sign-in is read off the request those events carry.
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

from tests.support.served import CONSENT_CLIENT_ID
from xtr_security_openid_connect_server.prompt import consent_required
from xtr_security_openid_connect_server.request_types.open_id_authorization_request import (
    OpenIdAuthorizationRequest,
)

from .config import USER_IDENTIFIER, USER_PASSWORD

__all__ = ["CONSENT_PAGE", "ask_for_consent", "resolve_user"]

CONSENT_PAGE: Final = "Allow this client?"
"""What the end-user is shown when this deployment has to ask for their consent."""


@as_event_listener(OAuth2Events.USER_RESOLVE)
async def resolve_user(event: UserResolveEvent) -> None:
    """Check the credentials that establish the resource owner."""
    if event.get_username() != USER_IDENTIFIER or event.get_password() != USER_PASSWORD:
        return
    _ = event.set_user(InMemoryUser(USER_IDENTIFIER, roles=["ROLE_USER"]))


@as_event_listener(OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE)
async def ask_for_consent(event: AuthorizationRequestResolveEvent) -> None:
    """Approve the request, or answer the client whose consent this deployment lacks."""
    if _consent_was_given(event):
        _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)

        return
    asked = _asked_of_the_sign_in(event)
    if "none" in asked:
        # No page may be shown, so the client is told instead.
        raise consent_required(event)
    _ = event.set_response(await _consent_page(asked))


def _consent_was_given(event: AuthorizationRequestResolveEvent) -> bool:
    """Tell whether this deployment already holds the consent the request needs.

    It holds it for every client but ``CONSENT_CLIENT_ID``, which stands for
    one the end-user never approved; a deployment reads a record of its own
    here, for this resource owner, this client and these scopes.
    """
    return event.get_client().get_identifier() != CONSENT_CLIENT_ID


def _asked_of_the_sign_in(event: AuthorizationRequestResolveEvent) -> frozenset[str]:
    """Return the ``prompt`` the request carried, empty when it is no sign-in."""
    request = event.get_authorization_request()
    if isinstance(request, OpenIdAuthorizationRequest):
        return request.get_prompt()

    return frozenset()


async def _consent_page(asked: frozenset[str]) -> Response:
    """Return the page asking for consent, naming the ``prompt`` it was asked with.

    The values named are the closed set the provider reads the parameter into,
    so the page repeats nothing the request wrote.
    """
    page = Response(200).with_header("content-type", "text/plain")
    _ = await page.get_body().write(f"{CONSENT_PAGE} prompt={' '.join(sorted(asked))}".encode())

    return page
