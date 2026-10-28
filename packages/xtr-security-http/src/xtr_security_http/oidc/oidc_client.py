"""An HTTP client for OpenID Connect protocol operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override
from xtr_http_client_contracts.exception import DecodingError, TransportError
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.exception.oidc_invalid_grant_error import OidcInvalidGrantError
from xtr_security_http.oauth2.access_token_type.bearer_token_type import BearerTokenType

from .oidc_client_interface import OidcClientInterface
from .oidc_discovery import OidcDiscovery

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from xtr_http_client_contracts import HttpClientInterface, HttpResponseInterface, RequestOptions

    from xtr_security_http.oauth2.access_token_type.access_token_type_interface import (
        AccessTokenTypeInterface,
    )
    from xtr_security_http.oauth2.client_authentication.client_authentication_interface import (
        ClientAuthenticationInterface,
    )

__all__ = ["OidcClient"]

_TOKEN_ENDPOINT: Final = "token_endpoint"  # noqa: S105 -- a metadata member name, not a credential
"""The metadata member naming the endpoint every grant is made at."""

_PROOF_ENDPOINTS: Final = frozenset({_TOKEN_ENDPOINT, "pushed_authorization_request_endpoint"})
"""The endpoints RFC 9449 carries a proof to, its Section 5 and its Section 10.1."""

_CLIENT_ERROR: Final = 400
"""Where the client-error status range starts, RFC 9110, Section 15.5."""

_SERVER_ERROR: Final = 500
"""Where the server-error status range starts, RFC 9110, Section 15.6."""


@final
class OidcClient(OidcClientInterface):
    """The OpenID Connect protocol operations, over the injected HTTP client.

    How the client authenticates at the token endpoint (RFC 6749, Section
    2.3) is a property of its registration at the provider, not of this class:
    it is injected, so that sending a secret, sending nothing at all, signing
    an assertion (OIDC Core 1.0, Section 9) or letting the provider read the
    certificate of the TLS handshake (RFC 8705, Section 2) are the same
    client with a different dependency.

    The client certificate is not part of that dependency, since a client may
    present one without authenticating with it (RFC 8705, Section 4). It is
    sent with each request made here, and these requests then go to the
    mutual-TLS aliases of the endpoints (RFC 8705, Section 5).

    What kind of access token it asks for is another such property (RFC 6749,
    Section 7.1): a bearer token (RFC 6750). A token bound to a key a proof
    factory signs for waits for the proof machinery this workspace has not
    aligned yet, and is not asked for here.
    """

    __slots__ = (
        "_access_token_type",
        "_certificate_options",
        "_client_authentication",
        "_client_id",
        "_discovery",
        "_http_client",
    )

    def __init__(
        self,
        http_client: HttpClientInterface,
        discovery: OidcDiscovery,
        client_id: str,
        client_authentication: ClientAuthenticationInterface,
        certificate_options: Mapping[str, object] | None = None,
    ) -> None:
        """Record the client, the discovery, the registration and the certificate options.

        Args:
            http_client: The client the provider's endpoints are reached with.
            discovery: Reads the endpoints off the provider's discovery
                document.
            client_id: The client's identifier, its registration at the
                provider.
            client_authentication: How the client authenticates at the token
                endpoint.
            certificate_options: The ``local_cert``, ``local_pk`` and
                ``passphrase`` request options of the client certificate, or
                none — and with none, the provider's own endpoints are used
                rather than their mutual-TLS aliases.
        """
        self._http_client = http_client
        self._discovery = discovery
        self._client_id = client_id
        self._client_authentication = client_authentication
        self._certificate_options = dict(certificate_options or {})
        # A bearer token: the one access token type this workspace aligns.
        # The type is a property of the client all the same, so it lives here
        # rather than at each call site, and a bound token is a type swapped
        # in when the proof machinery lands.
        self._access_token_type: AccessTokenTypeInterface = BearerTokenType()

    @override
    def get_client_authentication_method(self) -> str:
        """Return the name of the method the client authenticates with at the token endpoint."""
        return self._client_authentication.get_method()

    @override
    async def request(
        self,
        endpoint: str,
        body: Mapping[str, object] | None = None,
        options: Mapping[str, object] | None = None,
    ) -> HttpResponseInterface:
        """Make a client-authenticated POST to an endpoint the provider announces.

        The client is authenticated again on each attempt: a client assertion
        carries a ``jti`` a provider remembers (RFC 7523, Section 3), so
        sending the same one twice is a replay.

        Raises:
            AuthenticationError: When the endpoint is not announced by the
                provider, or does not use HTTPS.
        """
        url = await self._endpoint(endpoint)
        # The client authentication is told the token endpoint whatever is
        # requested: an assertion names the audience its registration says,
        # not the endpoint being called.
        token_endpoint = (
            url if endpoint == _TOKEN_ENDPOINT else await self._endpoint(_TOKEN_ENDPOINT)
        )

        async def send() -> HttpResponseInterface:
            merged = dict(options or {})
            # The registration wins over a body carrying a client of its own,
            # and the certificate over the request options: both are the
            # client's own, not the caller's.
            merged["body"] = {**(body or {}), "client_id": self._client_id}
            merged["max_redirects"] = 0
            merged = self._client_authentication.authenticate(
                self._client_id,
                token_endpoint,
                merged,
            )
            if endpoint in _PROOF_ENDPOINTS:
                merged = self._access_token_type.prepare_token_request(url, merged)
            merged.update(self._certificate_options)
            return await self._http_client.request(
                "POST",
                url,
                **cast("RequestOptions", cast("object", merged)),
            )

        return await self._retry(url, send)

    @override
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, object]:
        """Exchange an authorization code for tokens at the token endpoint.

        Raises:
            AuthenticationError: When the token endpoint is missing, cannot
                be reached or returns an invalid response.
        """
        body: dict[str, object] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier is not None:
            body["code_verifier"] = code_verifier
        response = await self._requested(_TOKEN_ENDPOINT, body)
        token_response = await self._members(response, "token")
        self._access_token_type.check_token_response(token_response)
        return token_response

    @override
    async def refresh_token(
        self,
        refresh_token: str,
        scopes: Sequence[str] = (),
    ) -> dict[str, object]:
        """Renew an access token with the refresh token grant of RFC 6749, Section 6.

        Raises:
            OidcInvalidGrantError: When the provider no longer honors the
                refresh token.
            AuthenticationError: When the token endpoint is missing, cannot
                be reached or returns an invalid response.
        """
        body: dict[str, object] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if scopes:
            body["scope"] = " ".join(scopes)
        response = await self._requested(_TOKEN_ENDPOINT, body)
        # RFC 6749, Section 5.2: "invalid_grant" is the one error saying the
        # refresh token itself is gone, where every other failure only means
        # the request may be tried again; the status code is checked first so
        # that a provider error page is never parsed as a token response.
        status = response.get_status_code()
        if _CLIENT_ERROR <= status < _SERVER_ERROR:
            members = await self._members(response, "token", throw=False)
            if members.get("error") == "invalid_grant":
                raise OidcInvalidGrantError(
                    "The OIDC provider rejected the refresh token: it expired, it was "
                    "revoked, or it was issued to another client.",
                )
        token_response = await self._members(response, "token")
        self._access_token_type.check_token_response(token_response)
        return token_response

    @override
    async def fetch_user_info(self, access_token: str) -> dict[str, object]:
        """Fetch the user's claims from the OIDC provider's userinfo endpoint.

        Raises:
            AuthenticationError: When the userinfo endpoint is missing,
                cannot be reached or returns an invalid response.
        """
        user_info_endpoint = await self._endpoint("userinfo_endpoint")
        options: dict[str, object] = self._access_token_type.present_token(
            access_token,
            "GET",
            user_info_endpoint,
            {"max_redirects": 0},
        )

        async def send() -> HttpResponseInterface:
            # The certificate wins over what the type prepared, the
            # certificate being the client's own, not the token's.
            merged = {**options, **self._certificate_options}
            return await self._http_client.request(
                "GET",
                user_info_endpoint,
                **cast("RequestOptions", cast("object", merged)),
            )

        try:
            response = await self._retry(user_info_endpoint, send)
        except (TransportError, DecodingError) as error:
            raise AuthenticationError(
                f'The OIDC userinfo endpoint request failed: "{error}"',
            ) from error
        return await self._members(response, "userinfo")

    async def _endpoint(self, endpoint: str) -> str:
        """Return the URL of an endpoint, or of its mutual-TLS alias.

        The alias is used when the client presents a certificate and the
        provider announces one (RFC 8705, Section 5), and checked again here,
        as the document may have been cached by a discovery checking no
        alias.
        """
        aliases = (
            (await self._discovery.get_configuration()).get("mtls_endpoint_aliases")
            if self._certificate_options
            else None
        )
        aliases = cast("dict[str, object]", aliases) if isinstance(aliases, dict) else None
        if aliases is not None and endpoint in aliases:
            alias = aliases[endpoint]
            if not isinstance(alias, str) or not OidcDiscovery.is_secure_url(alias):
                raise AuthenticationError(
                    f'The "mtls_endpoint_aliases.{endpoint}" announced by the OIDC '
                    "provider must be an HTTPS URL.",
                )
            return alias
        return await self._discovery.get_secure_endpoint(endpoint)

    async def _retry(
        self,
        url: str,
        send: Callable[[], Awaitable[HttpResponseInterface]],
    ) -> HttpResponseInterface:
        """Send a request, once more when the access token type says so.

        A server may answer a first request with what the next one has to
        carry, and the type is what knows it: it reads every response, keeps
        what it named, and says whether the request is to be built and sent
        again. At most one repeat: a server that named what the next request
        must carry answers the request carrying it, and a second refusal is a
        refusal and not an instruction.
        """
        response = await send()
        # The bearer type never asks for a second round; a bound type lands
        # with the proof machinery.
        if self._access_token_type.on_response(response, url):  # pragma: no cover
            response = await send()
            _ = self._access_token_type.on_response(response, url)
        return response

    async def _requested(
        self,
        endpoint: str,
        body: dict[str, object],
    ) -> HttpResponseInterface:
        """Make one client-authenticated request, wrapping what the transfer fails with.

        Raises:
            AuthenticationError: When the endpoint cannot be reached.
        """
        try:
            return await self.request(endpoint, body)
        except (TransportError, DecodingError) as error:
            raise AuthenticationError(
                f'The OIDC token endpoint request failed: "{error}"',
            ) from error

    async def _members(
        self,
        response: HttpResponseInterface,
        endpoint: str,
        *,
        throw: bool = True,
    ) -> dict[str, object]:
        """Read a response's body as the JSON object an endpoint answers with.

        Raises:
            AuthenticationError: When the body cannot be read as one.
        """
        try:
            async with response:
                return await response.to_array(throw=throw)
        except (TransportError, DecodingError) as error:
            raise AuthenticationError(
                f'The OIDC {endpoint} endpoint request failed: "{error}"',
            ) from error
