"""The bridges between what the protocol asks for and what is stored.

Each one implements a contract from
:mod:`xtr_security_oauth2_server.repositories` — the surface the grants, the
servers and the validators reach storage through — over the managers in
:mod:`xtr_security_oauth2_server.manager`. That is the whole of the seam: the
protocol knows the contracts, a deployment chooses the managers, and these
translate between an entity that lives for one request and a record that
outlives it.

Three of them are also where the application gets a word in, because the
answer genuinely is not this package's to give: which scopes a token ends up
with, whose credentials these are, and what else a token should say.

``NullAccessTokenRepository`` is the access-token bridge of a deployment that
writes no access token down, and gives up revoking them in exchange.
"""

from __future__ import annotations

from .access_token_repository import AccessTokenRepository
from .auth_code_repository import AuthCodeRepository
from .client_repository import ClientRepository
from .device_code_repository import DeviceCodeRepository
from .null_access_token_repository import NullAccessTokenRepository
from .refresh_token_repository import RefreshTokenRepository
from .scope_repository import ScopeRepository
from .user_repository import UserRepository

__all__ = [
    "AccessTokenRepository",
    "AuthCodeRepository",
    "ClientRepository",
    "DeviceCodeRepository",
    "NullAccessTokenRepository",
    "RefreshTokenRepository",
    "ScopeRepository",
    "UserRepository",
]
