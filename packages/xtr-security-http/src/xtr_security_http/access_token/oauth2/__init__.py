"""Introspecting bearer tokens on an OAuth2 authorization server (RFC 7662).

The plain introspection flow needs nothing beyond the package's own
dependencies: the HTTP client and the cache are the contracts the application
wires behind it. Only verifying signed introspection responses (RFC 9701) needs
joserfc, which the ``oidc`` extra carries — the handler names the extra when it
is asked to verify without it.
"""

from __future__ import annotations

from .oauth2_token_handler import Oauth2TokenHandler

__all__ = ["Oauth2TokenHandler"]
