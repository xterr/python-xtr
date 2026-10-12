"""What this server keeps about its clients and the credentials it issued.

The stored side of the protocol. Each of these is a plain record with
accessors — a client's registration, an access token, an authorization code, a
refresh token, a device code — and every one of them is reachable only through
a manager, so an application chooses where they live without the protocol
knowing.

They are deliberately not the library's entities. An entity is what a grant
reads and writes while it handles one request; a model is what survives the
request. The repository bridges turn one into the other, and that seam is what
lets the entities stay about the protocol while the models stay about storage —
a client model carries an active flag and a secret hash no grant should see,
and an access-token entity can sign itself while a stored one only remembers
that it was issued.

``AbstractClient`` is the one meant to be extended: a deployment needing
columns of its own derives from it and names the result in the bundle's
``client.classname`` setting. ``Client`` is the subclass shipped for everyone
else.
"""

from __future__ import annotations

from .abstract_client import AbstractClient
from .access_token import AccessToken
from .access_token_interface import AccessTokenInterface
from .authorization_code import AuthorizationCode
from .authorization_code_interface import AuthorizationCodeInterface
from .client import Client
from .client_interface import ClientInterface
from .device_code import DeviceCode
from .device_code_interface import DeviceCodeInterface
from .refresh_token import RefreshToken
from .refresh_token_interface import RefreshTokenInterface

__all__ = [
    "AbstractClient",
    "AccessToken",
    "AccessTokenInterface",
    "AuthorizationCode",
    "AuthorizationCodeInterface",
    "Client",
    "ClientInterface",
    "DeviceCode",
    "DeviceCodeInterface",
    "RefreshToken",
    "RefreshTokenInterface",
]
