"""A security token that hands back the credentials it was proved by."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["CredentialedTokenInterface"]


@runtime_checkable
class CredentialedTokenInterface(Protocol):
    """A token that keeps the credentials its authentication settled on.

    The token manager reads a presented token's claims out of whatever a firewall
    settled on, and the only part of a security token it needs is the compact
    token itself. The authenticator's own
    :class:`~xtr_security_jwt.security.authenticator.token.jwt_post_authentication_token.JwtPostAuthenticationToken`
    answers this; a token of another kind carries no compact token, and the
    manager reports it as carrying no claims.

    This is a structural interface on purpose: it names the one method the
    manager calls, so the crypto layer never has to import the HTTP edge the
    concrete token lives in.
    """

    def get_credentials(self) -> object:
        """Return the credentials this authentication was proved by."""
        ...
