"""The concrete entities this package ships, composed out of the shipped traits.

The library side of the seam: these are what a grant reads and writes while it
handles one request, and what the repository bridges mint, fill from storage
and read back. An application may bring its own instead — the contracts in
:mod:`xtr_security_oauth2_server.entities` are what a grant depends on — but a
deployment using the managers here gets these.

Every one of them is built with no arguments and filled through setters,
because that is how a repository works: mint the entity the deployment
configured, then put what was stored, or what the protocol just decided, onto
it.
"""

from __future__ import annotations

from .access_token import AccessToken
from .auth_code import AuthCode
from .client import Client
from .device_code import DeviceCode
from .refresh_token import RefreshToken
from .scope import Scope
from .user import User

__all__ = [
    "AccessToken",
    "AuthCode",
    "Client",
    "DeviceCode",
    "RefreshToken",
    "Scope",
    "User",
]
