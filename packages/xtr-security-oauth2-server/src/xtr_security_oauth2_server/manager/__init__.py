"""Where the stored models live, one contract per kind of thing kept.

The storage half of this package. The protocol never comes here: the
repository bridges in :mod:`xtr_security_oauth2_server.repository` do, and a
deployment chooses where its clients, tokens and codes actually live by
choosing managers.

Six contracts, each with no more than the protocol needs — find, save, sweep,
and for clients the administration a person does. The refresh-token one adds
an atomic revoke, because two refreshes of one token must not both succeed.

:mod:`xtr_security_oauth2_server.manager.in_memory` holds everything in the
process, for tests and demonstrations;
:mod:`xtr_security_oauth2_server.manager.orm` keeps it in a database, which is
what a deployment of more than one worker needs;
:mod:`xtr_security_oauth2_server.manager.null` is an access-token manager that
stores nothing, which an application keeping its credentials in stores of its
own names as ``CustomPersistenceConfig(access_token_manager=...)`` when it keeps
no access token. The bundle never wires it itself: with access tokens not
persisted it registers a repository bridge that keeps none instead.
"""

from __future__ import annotations

from .access_token_manager_interface import AccessTokenManagerInterface
from .authorization_code_manager_interface import AuthorizationCodeManagerInterface
from .client_filter import ClientFilter
from .client_manager_interface import ClientManagerInterface
from .device_code_manager_interface import DeviceCodeManagerInterface
from .refresh_token_manager_interface import RefreshTokenManagerInterface
from .scope_manager_interface import ScopeManagerInterface

__all__ = [
    "AccessTokenManagerInterface",
    "AuthorizationCodeManagerInterface",
    "ClientFilter",
    "ClientManagerInterface",
    "DeviceCodeManagerInterface",
    "RefreshTokenManagerInterface",
    "ScopeManagerInterface",
]
