"""The events the bundle layer announces, one per decision an application makes.

Each one is dispatched under its name from
:class:`~xtr_security_oauth2_server.oauth2_events.OAuth2Events`, carries what
a listener needs to decide, and is read back for the answer. Registering a
listener under the same name is the whole of the contract — the library never
learns what listens.
"""

from __future__ import annotations

from .access_token_extra_claims_resolve_event import AccessTokenExtraClaimsResolveEvent
from .authorization_request_resolve_event import AuthorizationRequestResolveEvent
from .authorization_request_resolve_event_factory import AuthorizationRequestResolveEventFactory
from .pre_save_client_event import PreSaveClientEvent
from .scope_resolve_event import ScopeResolveEvent
from .token_request_resolve_event import TokenRequestResolveEvent
from .user_resolve_event import UserResolveEvent

__all__ = [
    "AccessTokenExtraClaimsResolveEvent",
    "AuthorizationRequestResolveEvent",
    "AuthorizationRequestResolveEventFactory",
    "PreSaveClientEvent",
    "ScopeResolveEvent",
    "TokenRequestResolveEvent",
    "UserResolveEvent",
]
