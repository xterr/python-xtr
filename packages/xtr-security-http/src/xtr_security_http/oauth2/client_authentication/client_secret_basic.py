"""Sends the client identifier and secret as HTTP Basic credentials."""

from __future__ import annotations

from typing import final
from urllib.parse import quote

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .client_authentication_interface import ClientAuthenticationInterface

__all__ = ["ClientSecretBasic"]


@final
class ClientSecretBasic(ClientAuthenticationInterface):
    """Sends the client identifier and secret as HTTP Basic credentials.

    This is the "client_secret_basic" method of RFC 6749, Section 2.3.1, the
    one the RFC requires providers to support and recommends clients to use.

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
        """Build the HTTP Basic credentials of RFC 6749, Section 2.3.1.

        The client identifier and the secret are each percent-encoded before
        being combined, so that a colon, a percent sign or a non-ASCII byte
        in either of them survives the round trip.

        Args:
            client_id: The client the request is made for.
            token_endpoint: The endpoint the request is made to.
            options: The request options the request is about to be made with.

        Returns:
            The request options, carrying the credentials under "auth_basic".
        """
        del token_endpoint
        options["auth_basic"] = f"{quote(client_id, safe='')}:{quote(self._client_secret, safe='')}"
        return options

    @override
    def get_method(self) -> str:
        """Return the RFC 7591, Section 2 name: "client_secret_basic"."""
        return "client_secret_basic"
