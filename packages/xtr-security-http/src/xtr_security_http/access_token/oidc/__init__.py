"""Verifying bearer tokens from third-party OIDC issuers (needs the ``oidc`` extra).

Importing this subpackage requires joserfc and httpx, brought by the ``oidc``
extra of xtr-security-http. Importing :mod:`xtr_security_http` itself pulls in
neither; only reaching in here does, so an application that never verifies OIDC
tokens carries no JOSE or HTTP-client dependency.

The key material lives with the authenticator and discovery it serves —
:mod:`xtr_security_http.authenticator.oidc` and :mod:`xtr_security_http.oidc` —
and is re-exported here so the whole OIDC surface is reachable from one place.
"""

from __future__ import annotations

try:
    import httpx as _httpx
    import joserfc as _joserfc
except ImportError as _error:  # pragma: no cover -- exercised in a subprocess without the extra
    raise ImportError(
        "The OIDC access-token handler needs joserfc and httpx; install the 'oidc' extra: "
        'uv add "xtr-security-http[oidc]".',
    ) from _error
else:
    del _httpx, _joserfc

from xtr_security_http.authenticator.oidc.oidc_jwks import (
    OidcKeySetProviderInterface,
    StaticOidcKeySetProvider,
)
from xtr_security_http.oidc.oidc_discovery import DiscoveryOidcKeySetProvider

from .exception.oidc_key_set_error import OidcKeySetError
from .oidc_token_handler import OidcTokenHandler

__all__ = [
    "DiscoveryOidcKeySetProvider",
    "OidcKeySetError",
    "OidcKeySetProviderInterface",
    "OidcTokenHandler",
    "StaticOidcKeySetProvider",
]
