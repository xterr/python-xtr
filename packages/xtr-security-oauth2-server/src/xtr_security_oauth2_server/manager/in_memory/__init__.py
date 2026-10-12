"""Managers that keep everything in this process.

For tests and single-process demonstrations. Nothing here survives the
process, and a second process shares none of it — so a deployment that runs
more than one worker gets a server whose tokens exist on whichever worker
issued them.

Every one of them behaves like the stored managers in every way that matters:
clients are announced before they are saved, expiry is read off a clock rather
than off the machine, and a refresh token is revoked by exactly one caller.
"""

from __future__ import annotations

from .access_token_manager import AccessTokenManager
from .authorization_code_manager import AuthorizationCodeManager
from .client_manager import ClientManager
from .device_code_manager import DeviceCodeManager
from .refresh_token_manager import RefreshTokenManager
from .scope_manager import ScopeManager

__all__ = [
    "AccessTokenManager",
    "AuthorizationCodeManager",
    "ClientManager",
    "DeviceCodeManager",
    "RefreshTokenManager",
    "ScopeManager",
]
