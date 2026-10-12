"""Managers that keep everything in a database, through the ORM.

What a deployment of more than one worker needs: the clients, tokens and codes
live where every worker can read them, so a token issued by one is accepted by
another and a revocation reaches both.

Each of them reads and writes the stored models through the session of the unit
of work it is in, mapped by
:class:`~xtr_security_oauth2_server.persistence.mapping.driver.Driver`, and each
commits its own writes — a credential is stored before it is handed out, and a
device code's last poll is stored even when the answer to that poll is an
error. The scopes a deployment makes available stay in the process: they are
configuration, the same on every worker, and a table of them would only be a
copy.
"""

from __future__ import annotations

from .access_token_manager import AccessTokenManager
from .authorization_code_manager import AuthorizationCodeManager
from .client_manager import ClientManager
from .device_code_manager import DeviceCodeManager
from .refresh_token_manager import RefreshTokenManager

__all__ = [
    "AccessTokenManager",
    "AuthorizationCodeManager",
    "ClientManager",
    "DeviceCodeManager",
    "RefreshTokenManager",
]
