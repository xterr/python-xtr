"""Sends no client credentials, for a public client."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .client_authentication_interface import ClientAuthenticationInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["NoClientAuthentication"]


@final
class NoClientAuthentication(ClientAuthenticationInterface):
    """Sends no client credentials, for a public client.

    A public client cannot keep a secret confidential (RFC 6749, Section 2.1),
    so it is only identified by the "client_id" the token request always
    carries. This is the "none" method of RFC 7591, Section 2.

    Nothing else then binds the authorization code to the client, so PKCE
    (RFC 7636) is what protects the exchange: a code intercepted on the
    redirect cannot be redeemed without the code verifier. Exchanging a code
    without one is therefore refused here, which is the one request of a
    public client this refuses.

    """

    __slots__ = ()

    @override
    def authenticate(
        self,
        client_id: str,
        token_endpoint: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        """Refuse an authorization code redeemed without a PKCE verifier.

        The presence of the verifier is checked next to the grant naming the
        code. What a public client sends otherwise carries a secret of its
        own that no interception of the redirect yields: a refresh token, a
        device code, or the token it asks a provider to revoke.

        Args:
            client_id: The client the request is made for.
            token_endpoint: The endpoint the request is made to.
            options: The request options the request is about to be made
                with, carrying the token request body under the "body" key.

        Returns:
            The same request options — nothing is added.

        Raises:
            InvalidArgumentError: When the body redeems an authorization code
                and carries no "code_verifier".
        """
        del client_id, token_endpoint
        raw_body = options.get("body")
        body: Mapping[str, object] = (
            cast("Mapping[str, object]", raw_body) if isinstance(raw_body, dict) else {}
        )
        redeems_a_code: bool = body.get("grant_type") == "authorization_code" or "code" in body
        if redeems_a_code and not body.get("code_verifier"):
            raise InvalidArgumentError(
                "A public OAuth2 client must exchange the authorization code with PKCE, "
                "as it sends no client secret. Pass the code verifier with the code "
                "exchange, or authenticate the client with a secret.",
            )
        return options

    @override
    def get_method(self) -> str:
        """Return the RFC 7591, Section 2 name: "none", and no variation of it.

        The value is read to make a security decision and compared exactly,
        so a public client cannot pass for a confidential one by spelling
        the method differently.
        """
        return "none"
