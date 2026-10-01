"""The names this library's events are dispatched and listened to under.

Each name is the qualified class name of the event it stands for (the
repository's convention, :func:`~xtr_event_dispatcher_contracts.event_name_of`),
so a subscriber names the constant rather than importing the event class only to
name it. The two authentication-outcome names — issuing a token and refusing
one — likewise stand for the events an application dispatches around a token
endpoint.
"""

from __future__ import annotations

from typing import Final

from xtr_event_dispatcher_contracts import event_name_of

from .event.authentication_failure_event import AuthenticationFailureEvent
from .event.authentication_success_event import AuthenticationSuccessEvent
from .event.jwt_authenticated_event import JwtAuthenticatedEvent
from .event.jwt_created_event import JwtCreatedEvent
from .event.jwt_decoded_event import JwtDecodedEvent
from .event.jwt_encoded_event import JwtEncodedEvent
from .event.jwt_expired_event import JwtExpiredEvent
from .event.jwt_invalid_event import JwtInvalidEvent
from .event.jwt_not_found_event import JwtNotFoundEvent

__all__ = ["Events"]


class Events:
    """The event names, one constant per event this library dispatches.

    A subscriber names a constant to listen; the token manager and the
    authenticator dispatch under the same names.
    """

    #: A token's claims and headers, before it is signed.
    JWT_CREATED: Final[str] = event_name_of(JwtCreatedEvent)

    #: A token, once it has been signed.
    JWT_ENCODED: Final[str] = event_name_of(JwtEncodedEvent)

    #: A verified token's payload, which a listener may reject.
    JWT_DECODED: Final[str] = event_name_of(JwtDecodedEvent)

    #: A token that authenticated a request, with its payload.
    JWT_AUTHENTICATED: Final[str] = event_name_of(JwtAuthenticatedEvent)

    #: A token refused as invalid.
    JWT_INVALID: Final[str] = event_name_of(JwtInvalidEvent)

    #: A request that reached a protected resource carrying no token.
    JWT_NOT_FOUND: Final[str] = event_name_of(JwtNotFoundEvent)

    #: A token refused because it had expired.
    JWT_EXPIRED: Final[str] = event_name_of(JwtExpiredEvent)

    #: A token issued to a client, with the response data.
    AUTHENTICATION_SUCCESS: Final[str] = event_name_of(AuthenticationSuccessEvent)

    #: A token authentication that failed, with the response.
    AUTHENTICATION_FAILURE: Final[str] = event_name_of(AuthenticationFailureEvent)
