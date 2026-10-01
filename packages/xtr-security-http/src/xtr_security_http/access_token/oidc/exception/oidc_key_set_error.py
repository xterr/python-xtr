"""The keys that verify an OIDC token could not be obtained."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

__all__ = ["OidcKeySetError"]


class OidcKeySetError(SecurityError):
    """The verifying key set could not be fetched, discovered or read.

    Raised when a discovery document or a JWKS endpoint cannot be reached, an
    answer is not the JSON a key set is read from, or a discovered endpoint is
    not the ``https`` a key set is trusted to come over. The token handler turns
    it into an :class:`~xtr_security_http.exception.InvalidAccessTokenError`,
    since a token that cannot be verified cannot be trusted.
    """
