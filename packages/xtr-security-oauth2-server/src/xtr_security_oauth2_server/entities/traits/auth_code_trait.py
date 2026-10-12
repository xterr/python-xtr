"""An authorization code remembers the redirect URI it was asked for."""

from __future__ import annotations

__all__ = ["AuthCodeTrait"]


class AuthCodeTrait:
    """Holds the redirect URI an authorization code was issued for.

    ``None`` until something sets one, because a code issued for a client with
    a single registered URI, from a request that named none, has no URI to
    compare the token request against.
    """

    _redirect_uri: str | None = None

    def get_redirect_uri(self) -> str | None:
        """Return the redirect URI this code was issued for, or ``None``."""
        return self._redirect_uri

    def set_redirect_uri(self, uri: str) -> None:
        """Record that this code was issued for ``uri``."""
        self._redirect_uri = uri
