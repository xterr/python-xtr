"""How an OAuth 2.0 client authenticates itself at the token endpoint."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["ClientAuthenticationInterface"]


@runtime_checkable
class ClientAuthenticationInterface(Protocol):
    """How an OAuth 2.0 client authenticates itself at the token endpoint.

    A client registration carries exactly one such method, which RFC 7591,
    Section 2 names in its "token_endpoint_auth_method" metadata: a secret
    sent in the request body or as HTTP Basic credentials, nothing at all for a
    public client, a signed assertion (OIDC Core 1.0, Section 9), or a
    certificate presented in the TLS handshake (RFC 8705, Section 2). It is a
    property of the registration and not of the grant, so the same method
    authenticates every request to that endpoint.

    RFC 6749, Section 2.3 is the client authentication itself; RFC 7591,
    Section 2 is the metadata that names the method.
    """

    def authenticate(
        self,
        client_id: str,
        token_endpoint: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        """Apply the client-authentication method to a token endpoint request.

        A method is free to sign the request body, to move part of it into a
        header, or to leave it untouched: implementations get the request
        options the request is about to be made with, the body among them
        under the "body" key, and return the ones they want it made with
        instead.

        Args:
            client_id: The client the request is made for.
            token_endpoint: The endpoint the request is made to.
            options: The request options the request is about to be made
                with, carrying the token request body under the "body" key.

        Returns:
            The final request options.
        """
        ...

    def get_method(self) -> str:
        """Return the RFC 7591, Section 2 name of the method, e.g. "client_secret_basic".

        This is the value the client is registered with at the provider, and
        the one the provider announces support for in the
        "token_endpoint_auth_methods_supported" of its metadata.

        It is also read to make a security decision, and compared exactly: a
        method that authenticates with nothing must return "none" and no
        variation of it, or the client it belongs to silently escapes the
        rules a public client cannot bend — that it can turn off neither
        PKCE nor the ID token signature check.
        """
        ...
