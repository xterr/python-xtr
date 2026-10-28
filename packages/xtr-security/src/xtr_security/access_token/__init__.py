"""Token-handler factories: building the handler a bearer authenticator verifies with.

A :class:`TokenHandlerFactoryInterface` turns a token-handler configuration into
the service that turns a bearer token into a user badge; the built-ins are a
service handler (``id``), an OAuth2 introspection one (``oauth2``) and, when
the ``oidc`` extra is installed, an OIDC one and a userinfo one. A third-party
bundle registers its own through :func:`add_token_handler_factory`.
"""

from __future__ import annotations

from .oauth2_token_handler_factory import Oauth2TokenHandlerFactory
from .oidc_token_handler_factory import OidcTokenHandlerFactory
from .oidc_user_info_token_handler_factory import OidcUserInfoTokenHandlerFactory
from .service_token_handler_factory import ServiceTokenHandlerFactory
from .token_handler_factory_interface import TokenHandlerFactoryInterface

__all__ = [
    "Oauth2TokenHandlerFactory",
    "OidcTokenHandlerFactory",
    "OidcUserInfoTokenHandlerFactory",
    "ServiceTokenHandlerFactory",
    "TokenHandlerFactoryInterface",
]
