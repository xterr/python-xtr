"""The flows something a client holds is exchanged for a token through.

One grant per flow, each answering :class:`GrantTypeInterface`, so the
authorization server runs a request through whichever of them says it can
answer it and a deployment adds a flow by registering another one.

- :class:`AbstractGrant` — what every grant is built out of.
- :class:`AbstractAuthorizeGrant` — and what the two that redirect add to it.
- :class:`AuthCodeGrant` — a code in the browser, redeemed by the client.
- :class:`ClientCredentialsGrant` — a client acting for itself.
- :class:`DeviceCodeGrant` — a device polling while its owner approves it.
- :class:`ImplicitGrant` — the token handed to the browser; legacy.
- :class:`PasswordGrant` — the resource owner's own credentials; legacy.
- :class:`RefreshTokenGrant` — a refresh token spent for a new pair.
"""

from __future__ import annotations

from .abstract_authorize_grant import AbstractAuthorizeGrant
from .abstract_grant import DEFAULT_REFRESH_TOKEN_TTL, AbstractGrant
from .auth_code_grant import AuthCodeGrant
from .client_credentials_grant import ClientCredentialsGrant
from .device_code_grant import USER_CODE_ALPHABET, DeviceCodeGrant
from .grant_type_interface import GrantTypeInterface
from .implicit_grant import ImplicitGrant
from .password_grant import PasswordGrant
from .refresh_token_grant import RefreshTokenGrant

__all__ = [
    "DEFAULT_REFRESH_TOKEN_TTL",
    "USER_CODE_ALPHABET",
    "AbstractAuthorizeGrant",
    "AbstractGrant",
    "AuthCodeGrant",
    "ClientCredentialsGrant",
    "DeviceCodeGrant",
    "GrantTypeInterface",
    "ImplicitGrant",
    "PasswordGrant",
    "RefreshTokenGrant",
]
