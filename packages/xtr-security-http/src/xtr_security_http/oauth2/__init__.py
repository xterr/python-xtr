"""The client side of OAuth2: authenticating at the token endpoint, presenting the token.

This is the suite an application that *talks to* an authorization server
builds its client from — a different folder and a different concern from
:mod:`xtr_security_http.access_token.oauth2`, which is the resource server
verifying the tokens that arrive: this one never reads a token it was not
issued.

Everything exported here is importable with nothing beyond the package's own
dependencies. The assertion pair — :class:`ClientSecretJwt` and
:class:`PrivateKeyJwt`, over :class:`AbstractClientAssertion` — signs a JWT,
and needs joserfc, which the ``oidc`` extra carries: import it from
:mod:`.client_authentication.client_secret_jwt` and
:mod:`.client_authentication.private_key_jwt`, which name the extra when it
is missing.
"""

from __future__ import annotations

from .access_token_type import AccessTokenTypeInterface, BearerTokenType
from .client_authentication import (
    AbstractTlsClientAuth,
    ClientAuthenticationInterface,
    ClientSecretBasic,
    ClientSecretPost,
    NoClientAuthentication,
    SelfSignedTlsClientAuth,
    TlsClientAuth,
)
from .jws_algorithms import JwsAlgorithms

__all__ = [
    "AbstractTlsClientAuth",
    "AccessTokenTypeInterface",
    "BearerTokenType",
    "ClientAuthenticationInterface",
    "ClientSecretBasic",
    "ClientSecretPost",
    "JwsAlgorithms",
    "NoClientAuthentication",
    "SelfSignedTlsClientAuth",
    "TlsClientAuth",
]
