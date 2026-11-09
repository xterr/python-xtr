"""Records, on a sign-in's request, when the end-user last signed in."""

from __future__ import annotations

from typing import Final

# The dispatcher reads the listener's signature at runtime to find its event
# and to fill the security facade from the container, so both stay importable
# here.
from xtr_dependency_injection import Injected  # noqa: TC002
from xtr_event_dispatcher import as_event_listener
from xtr_security import Security  # noqa: TC002
from xtr_security_oauth2_server.event.authorization_request_resolve_event import (  # noqa: TC002
    AuthorizationRequestResolveEvent,
)
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

from xtr_security_openid_connect_server.request_types.open_id_authorization_request import (
    OpenIdAuthorizationRequest,
)

__all__ = ["AUTH_TIME_LISTENER_PRIORITY", "stamp_auth_time"]

#: The priority the sign-in time is recorded at. A consent listener decides the
#: request and stops the listeners after it, so this one has to run first: a
#: consent listener runs at a lower priority — the default ``0`` does.
AUTH_TIME_LISTENER_PRIORITY: Final = 2048


@as_event_listener(OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE, priority=AUTH_TIME_LISTENER_PRIORITY)
async def stamp_auth_time(
    event: AuthorizationRequestResolveEvent,
    security: Injected[Security],
) -> None:
    """Record when the end-user signed in on the request, if it is a sign-in.

    Every interactive login records the moment it proved a credential on the
    firewall's token, and a re-login adds a newer one, so the newest proof is
    the sign-in the ID token reports. A token proving nothing — a remembered
    login, which shows no credential — leaves the time unknown, and the ID
    token then states none.

    The facade is scoped to the request, so it is filled on every call, from
    the unit of work the authorization request arrived in. The listener only
    reads: the consent decision is left to the listeners after it.
    """
    request = event.get_authorization_request()
    if not isinstance(request, OpenIdAuthorizationRequest):
        return
    token = security.get_token()
    proven = token.get_authentication_proofs().values() if token is not None else ()
    request.set_auth_time(max(proven, default=None))
