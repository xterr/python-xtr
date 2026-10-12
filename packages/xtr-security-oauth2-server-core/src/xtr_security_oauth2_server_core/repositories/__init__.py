"""Where the authorization server keeps and reads its state.

Seven contracts, one per kind of thing this server has to remember, all
grouped under :class:`RepositoryInterface`. An application implements them
over whatever it already uses — a relational database, a cache, a remote
service — and the grants, the servers and the validators go through nothing
else to reach storage.

Every method is awaitable, because every one of them may reach that storage;
nothing here is a pure computation an implementation would be forced to make
async for no reason.

The entities the methods hand back are the application's own: a repository
mints them, so what a grant issues is the mapped class with the columns a
deployment needs, and the grant only fills in what the protocol decides.
"""

from __future__ import annotations

from .access_token_repository_interface import AccessTokenRepositoryInterface
from .auth_code_repository_interface import AuthCodeRepositoryInterface
from .client_repository_interface import ClientRepositoryInterface
from .device_code_repository_interface import DeviceCodeRepositoryInterface
from .refresh_token_repository_interface import RefreshTokenRepositoryInterface
from .repository_interface import RepositoryInterface
from .scope_repository_interface import ScopeRepositoryInterface
from .user_repository_interface import UserRepositoryInterface

__all__ = [
    "AccessTokenRepositoryInterface",
    "AuthCodeRepositoryInterface",
    "ClientRepositoryInterface",
    "DeviceCodeRepositoryInterface",
    "RefreshTokenRepositoryInterface",
    "RepositoryInterface",
    "ScopeRepositoryInterface",
    "UserRepositoryInterface",
]
