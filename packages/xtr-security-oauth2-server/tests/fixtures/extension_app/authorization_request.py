"""The authorization request of a deployment running the add-on."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server_core.request_types.authorization_request import AuthorizationRequest

__all__ = ["NonceAuthorizationRequest"]


@final
class NonceAuthorizationRequest(AuthorizationRequest):
    """Remembers the one parameter the add-on carries across the consent step.

    The request is the only state that crosses that step, so this is where a
    parameter of the original authorization request waits while the resource
    owner decides. Everything else about the request is the shipped one's, and
    the grant goes on filling it in.
    """

    def __init__(self) -> None:
        """Start an empty request, carrying no parameter of the add-on's yet."""
        super().__init__()
        self._nonce: str | None = None

    def get_nonce(self) -> str | None:
        """Return the parameter the original request carried, or ``None``."""
        return self._nonce

    def set_nonce(self, nonce: str) -> None:
        """Record the parameter the original request carried."""
        self._nonce = nonce
