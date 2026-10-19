"""The OIDC client machinery: discovery, JWKS, verification, tokens, renewal and logout.

The client side of OpenID Connect — what an application that *talks to* a
provider builds its login flow from — as a different folder and a different
concern from :mod:`xtr_security_http.access_token.oidc`, which is the resource
server verifying the tokens that arrive. The back-channel logout — the
provider pushing the end of one of its sessions — is the client side too:
it is the login's tokens that carry what it names.

Importing this subpackage requires joserfc, brought by the ``oidc`` extra of
xtr-security-http: the key-set provider and the signature verifier read and
verify JOSE documents at import time. Importing
:mod:`xtr_security_http` itself pulls in neither; only reaching in here does,
so an application that never talks to an OIDC provider carries no JOSE
dependency.
"""

from __future__ import annotations

from .discovery_oidc_key_set_provider import DiscoveryOidcKeySetProvider
from .oidc_back_channel_logout import OidcBackChannelLogout
from .oidc_client import OidcClient
from .oidc_client_interface import OidcClientInterface
from .oidc_discovery import OidcDiscovery
from .oidc_ended_sessions import OidcEndedSessions
from .oidc_id_token import OidcIdToken
from .oidc_jwks import OidcJwks
from .oidc_logout_token import OidcLogoutToken
from .oidc_signature_verifier import OidcSignatureVerifier
from .oidc_token_refresher import OidcTokenRefresher

__all__ = [
    "DiscoveryOidcKeySetProvider",
    "OidcBackChannelLogout",
    "OidcClient",
    "OidcClientInterface",
    "OidcDiscovery",
    "OidcEndedSessions",
    "OidcIdToken",
    "OidcJwks",
    "OidcLogoutToken",
    "OidcSignatureVerifier",
    "OidcTokenRefresher",
]
