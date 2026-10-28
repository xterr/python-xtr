"""How an OAuth2 client authenticates itself at the token endpoint.

The methods that hold no key of their own are importable with nothing beyond
the package's own dependencies. The assertion pair —
:class:`ClientSecretJwt` and :class:`PrivateKeyJwt`, over
:class:`AbstractClientAssertion` — signs a JWT, and lives behind the
``oidc`` extra: import it from :mod:`.client_secret_jwt` and
:mod:`.private_key_jwt`, which name the extra when it is missing.
"""

from __future__ import annotations

from .abstract_tls_client_auth import AbstractTlsClientAuth
from .client_authentication_interface import ClientAuthenticationInterface
from .client_secret_basic import ClientSecretBasic
from .client_secret_post import ClientSecretPost
from .no_client_authentication import NoClientAuthentication
from .self_signed_tls_client_auth import SelfSignedTlsClientAuth
from .tls_client_auth import TlsClientAuth

__all__ = [
    "AbstractTlsClientAuth",
    "ClientAuthenticationInterface",
    "ClientSecretBasic",
    "ClientSecretPost",
    "NoClientAuthentication",
    "SelfSignedTlsClientAuth",
    "TlsClientAuth",
]
