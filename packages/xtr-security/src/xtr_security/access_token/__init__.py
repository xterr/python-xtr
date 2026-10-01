"""Token-handler factories: building the handler a bearer authenticator verifies with.

A :class:`TokenHandlerFactoryInterface` turns a token-handler configuration into
the service that turns a bearer token into a user badge; the built-ins are a
service handler (``id``) and, when the ``oidc`` extra is installed, an OIDC one.
A third-party bundle registers its own through :func:`add_token_handler_factory`.
"""

from __future__ import annotations

from .oidc_token_handler_factory import OidcTokenHandlerFactory
from .service_token_handler_factory import ServiceTokenHandlerFactory
from .token_handler_factory_interface import TokenHandlerFactoryInterface

__all__ = [
    "OidcTokenHandlerFactory",
    "ServiceTokenHandlerFactory",
    "TokenHandlerFactoryInterface",
]
