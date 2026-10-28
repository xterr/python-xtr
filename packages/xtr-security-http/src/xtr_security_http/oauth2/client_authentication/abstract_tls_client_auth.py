"""Authenticates the client with the certificate it presents in the TLS handshake."""

from __future__ import annotations

from abc import abstractmethod
from typing import final

from typing_extensions import override

from .client_authentication_interface import ClientAuthenticationInterface

__all__ = ["AbstractTlsClientAuth"]


class AbstractTlsClientAuth(  # pyright: ignore[reportImplicitAbstractClass]  -- subclasses implement get_method
    ClientAuthenticationInterface,
):
    """Authenticates the client with the certificate it presents in the TLS handshake.

    Nothing is added to the request: the provider reads the certificate from
    the handshake, and the "client_id" names the registration it is checked
    against. The certificate is not held here, since a client may present one
    without authenticating with it (Section 4): the HTTP client carries it,
    as its own request options — the certificate, its key and the key's
    passphrase — and every request the client makes presents it.

    RFC 8705, Section 2 is what this method is.
    """

    __slots__: tuple[str, ...] = ()

    @final
    @override
    def authenticate(
        self,
        client_id: str,
        token_endpoint: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        """Return the options unchanged: the handshake has already authenticated the client.

        Args:
            client_id: The client the request is made for.
            token_endpoint: The endpoint the request is made to.
            options: The request options the request is about to be made with.

        Returns:
            The same request options.
        """
        del client_id, token_endpoint
        return options

    @abstractmethod
    @override
    def get_method(self) -> str:
        """Return the RFC 7591, Section 2 name of the method."""
        ...
