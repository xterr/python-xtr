"""Authenticator factories: building a firewall's authenticators from configuration.

An :class:`AuthenticatorFactoryInterface` turns an authenticator configuration a
firewall lists into the services that authenticate its requests; the built-in
:class:`AccessTokenFactory` builds a bearer authenticator over a token handler.
A third-party bundle registers its own through :func:`add_authenticator_factory`.
"""

from __future__ import annotations

from .access_token_factory import AccessTokenFactory
from .authenticator_factory_interface import AuthenticatorFactoryInterface

__all__ = [
    "AccessTokenFactory",
    "AuthenticatorFactoryInterface",
]
