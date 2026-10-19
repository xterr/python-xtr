"""Authenticates the client with a certificate it signed itself."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from .abstract_tls_client_auth import AbstractTlsClientAuth

__all__ = ["SelfSignedTlsClientAuth"]


@final
class SelfSignedTlsClientAuth(AbstractTlsClientAuth):
    """Authenticates the client with a certificate it signed itself.

    This is the "self_signed_tls_client_auth" method of RFC 8705, Section 2.2:
    the provider matches the certificate against the keys the client
    registered.

    """

    __slots__ = ()

    @override
    def get_method(self) -> str:
        """Return the RFC 7591, Section 2 name: "self_signed_tls_client_auth"."""
        return "self_signed_tls_client_auth"
