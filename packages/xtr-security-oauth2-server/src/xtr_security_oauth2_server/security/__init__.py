"""The resource-server side: proving a caller by the access token it presented.

An application names :class:`OAuth2AuthenticatorConfig` on a firewall and the
bundle builds one :class:`OAuth2Authenticator` for it, over that firewall's own
user provider. Everything here is what that authentication produces or raises.
"""

from __future__ import annotations

from .authentication.token.oauth2_token import OAuth2Token
from .authenticator.oauth2_authenticator import OAuth2Authenticator
from .exception.oauth2_authentication_error import OAuth2AuthenticationError
from .exception.oauth2_authentication_failed_error import OAuth2AuthenticationFailedError
from .user.client_credentials_user import ClientCredentialsUser

__all__ = [
    "ClientCredentialsUser",
    "OAuth2AuthenticationError",
    "OAuth2AuthenticationFailedError",
    "OAuth2Authenticator",
    "OAuth2Token",
]
