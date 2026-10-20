"""Authenticator factories: building a firewall's authenticators from configuration.

An :class:`AuthenticatorFactoryInterface` turns an authenticator configuration a
firewall lists into the services that authenticate its requests; the built-ins
are :class:`AccessTokenFactory`, building a bearer authenticator over a token
handler, :class:`HttpBasicFactory`, building the browser's own credential
prompt, and — when the ``oidc`` extra is installed — :class:`OidcLoginFactory`,
building an authorization-code login. A third-party bundle registers its own
through :func:`add_authenticator_factory`.
"""

from __future__ import annotations

from .access_token_factory import AccessTokenFactory
from .authenticator_factory_interface import AuthenticatorFactoryInterface
from .http_basic_factory import HttpBasicFactory
from .oidc_login_factory import OidcLoginFactory
from .stateless_authenticator_factory_interface import StatelessAuthenticatorFactoryInterface

__all__ = [
    "AccessTokenFactory",
    "AuthenticatorFactoryInterface",
    "HttpBasicFactory",
    "OidcLoginFactory",
    "StatelessAuthenticatorFactoryInterface",
]
