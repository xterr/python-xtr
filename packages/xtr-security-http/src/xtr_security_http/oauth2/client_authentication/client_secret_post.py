"""Sends the client secret in the body of the token request."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .client_authentication_interface import ClientAuthenticationInterface

__all__ = ["ClientSecretPost"]


@final
class ClientSecretPost(ClientAuthenticationInterface):
    """Sends the client secret in the body of the token request.

    This is the "client_secret_post" method of RFC 6749, Section 2.3.1, which
    the RFC itself only tolerates: it recommends "client_secret_basic"
    instead. Use it for the providers that support nothing else.

    """

    __slots__ = ("_client_secret",)

    def __init__(self, client_secret: str) -> None:
        """Record the secret shared with the provider.

        Args:
            client_secret: The client's secret, as registered at the provider.

        Raises:
            InvalidArgumentError: When the secret is empty — a public client
                holds none, and declares itself with
                :class:`NoClientAuthentication`.
        """
        if not client_secret:
            raise InvalidArgumentError(
                "The OAuth2 client secret cannot be empty. Use NoClientAuthentication "
                "to declare a public client, which holds no secret.",
            )
        self._client_secret = client_secret

    @override
    def authenticate(
        self,
        client_id: str,
        token_endpoint: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        """Add the secret to the token request body, next to the "client_id" it travels with.

        Args:
            client_id: The client the request is made for.
            token_endpoint: The endpoint the request is made to.
            options: The request options the request is about to be made
                with, carrying the token request body under the "body" key.

        Returns:
            The request options, with "client_secret" added to the body.
        """
        del client_id, token_endpoint
        body = options.get("body")
        if not isinstance(body, dict):
            body = {}
            options["body"] = body
        body["client_secret"] = self._client_secret
        return options

    @override
    def get_method(self) -> str:
        """Return the RFC 7591, Section 2 name: "client_secret_post"."""
        return "client_secret_post"
