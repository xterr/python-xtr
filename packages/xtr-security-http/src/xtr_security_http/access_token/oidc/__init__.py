"""Signing and reading bearer tokens for OIDC issuers (needs the ``oidc`` extra).

Importing this subpackage requires joserfc, brought by the ``oidc``
extra of xtr-security-http. Importing :mod:`xtr_security_http` itself pulls in
neither; only reaching in here does, so an application that never signs or
verifies OIDC tokens carries no JOSE dependency. The userinfo handler needs
neither, but rides the extra with the subpackage it lives in — the price of
keeping the OIDC surface in one place.

The key material lives with the authenticator and discovery it serves —
:mod:`xtr_security_http.authenticator.oidc` and :mod:`xtr_security_http.oidc` —
and is re-exported here so the whole OIDC surface is reachable from one place.
"""

from __future__ import annotations

try:
    import joserfc as _joserfc
except ImportError as _error:  # pragma: no cover -- exercised in a subprocess without the extra
    raise ImportError(
        "The OIDC access-token pieces need joserfc; install the 'oidc' extra: "
        'uv add "xtr-security-http[oidc]".',
    ) from _error
else:
    del _joserfc

from xtr_security_http.authenticator.oidc.oidc_jwks import (
    OidcKeySetProviderInterface,
    StaticOidcKeySetProvider,
)
from xtr_security_http.oidc.discovery_oidc_key_set_provider import DiscoveryOidcKeySetProvider

from .exception.invalid_signature_error import InvalidSignatureError
from .exception.missing_claim_error import MissingClaimError
from .exception.oidc_key_set_error import OidcKeySetError
from .oidc_token_generator import OidcTokenGenerator
from .oidc_token_handler import OidcTokenHandler
from .oidc_trait import OidcTrait
from .oidc_user_info_token_handler import OidcUserInfoTokenHandler

__all__ = [
    "DiscoveryOidcKeySetProvider",
    "InvalidSignatureError",
    "MissingClaimError",
    "OidcKeySetError",
    "OidcKeySetProviderInterface",
    "OidcTokenGenerator",
    "OidcTokenHandler",
    "OidcTrait",
    "OidcUserInfoTokenHandler",
    "StaticOidcKeySetProvider",
]
