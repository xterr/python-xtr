"""The OpenID Connect protocol operations the login flow needs from a provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_client_contracts import HttpResponseInterface

__all__ = ["OidcClientInterface"]


@runtime_checkable
class OidcClientInterface(Protocol):
    """The OpenID Connect protocol operations the login flow needs from a provider.

    See OIDC Core 1.0, Section 3.1 for the flow these operations serve.
    """

    async def request(
        self,
        endpoint: str,
        body: Mapping[str, object] | None = None,
        options: Mapping[str, object] | None = None,
    ) -> HttpResponseInterface:
        """Make a client-authenticated POST to an endpoint the provider announces.

        Any grant this interface does not name is written on this call, as is
        anything else an endpoint answers: revoking a token, introspecting
        one, pushing an authorization request, or running a grant of its own.
        The raw response is returned, an endpoint being free to answer a JSON
        object, a signed JWT, or nothing at all, as RFC 7009, Section 2.2
        makes the answer of a revocation.

        Args:
            endpoint: The metadata member naming the endpoint, e.g.
                ``"revocation_endpoint"``.
            body: The form body, which the ``client_id`` is added to.
            options: The request options, over which the body, the redirects
                and what the registration contributes win.

        Raises:
            AuthenticationError: When the endpoint is not announced by the
                provider, or does not use HTTPS.
        """
        ...

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, object]:
        """Exchange an authorization code for tokens at the token endpoint.

        Returns:
            The members of the access-token response.

        Raises:
            AuthenticationError: When the token endpoint is missing, cannot
                be reached or returns an invalid response.
        """
        ...

    async def refresh_token(
        self,
        refresh_token: str,
        scopes: Sequence[str] = (),
    ) -> dict[str, object]:
        """Renew an access token with the refresh token grant of RFC 6749, Section 6.

        The provider may answer with a new refresh token, which then replaces
        the one given here, and with a new ID token, which OIDC Core 1.0,
        Section 12.2 constrains.

        Args:
            refresh_token: The token the grant is made with.
            scopes: The scopes of the new access token, which RFC 6749,
                Section 6 only allows to narrow the ones the refresh token was
                issued with; the original scopes are asked for when the
                sequence is empty.

        Returns:
            The members of the access-token response.

        Raises:
            OidcInvalidGrantError: When the provider no longer honors the
                refresh token.
            AuthenticationError: When the token endpoint is missing, cannot
                be reached or returns an invalid response.
        """
        ...

    async def fetch_user_info(self, access_token: str) -> dict[str, object]:
        """Fetch the user's claims from the OIDC provider's userinfo endpoint.

        Returns:
            The claims the endpoint answered with.

        Raises:
            AuthenticationError: When the userinfo endpoint is missing,
                cannot be reached or returns an invalid response.
        """
        ...

    def get_client_authentication_method(self) -> str:
        """Return the name of the method the client authenticates with at the token endpoint.

        The names are the ones RFC 7591, Section 2 registers, e.g.
        ``"client_secret_basic"``, or ``"none"`` for a public client. Whether
        the client holds a secret is what the security of the whole flow rests
        on, so the flow is entitled to ask, and to refuse to run with a
        configuration a public client cannot afford.
        """
        ...
