"""Authenticates the client with a certificate an authority issued to it."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from .abstract_tls_client_auth import AbstractTlsClientAuth

__all__ = ["TlsClientAuth"]


@final
class TlsClientAuth(AbstractTlsClientAuth):
    """Authenticates the client with a certificate a certificate authority issued to it.

    This is the "tls_client_auth" method of RFC 8705, Section 2.1: the
    provider validates the certificate chain, then matches the subject the
    client registered.

    """

    __slots__ = ()

    @override
    def get_method(self) -> str:
        """Return the RFC 7591, Section 2 name: "tls_client_auth"."""
        return "tls_client_auth"
