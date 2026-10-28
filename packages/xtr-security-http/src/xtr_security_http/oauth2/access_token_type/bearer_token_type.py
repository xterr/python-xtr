"""The bearer token of RFC 6750, which is used by whoever holds it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_security_core.exception import AuthenticationError

from .access_token_type_interface import AccessTokenTypeInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import HttpResponseInterface

__all__ = ["BearerTokenType"]

_TOKEN_TYPE: Final = "Bearer"  # noqa: S105 -- the RFC 6750 scheme name, not a credential
"""RFC 6750, Section 2.1: the scheme a bearer token travels under."""


@final
class BearerTokenType(AccessTokenTypeInterface):
    """Presents the access token as it is, in the "Authorization" header.

    Nothing is proven when it is presented, so nothing is signed and nothing
    is bound: the token travels in the header under the "Bearer" scheme
    (RFC 6750, Section 2.1), and the transport is what keeps it confidential.

    """

    __slots__ = ()

    @override
    def get_token_type(self) -> str:
        """Return the type this client presents: "Bearer"."""
        return _TOKEN_TYPE

    @override
    def check_token_response(self, token_response: Mapping[str, object]) -> None:
        """Refuse a token of another type, and accept a response naming none.

        RFC 6749, Section 5.1 makes "token_type" required, and a provider
        leaving it out is still handing out a token to be used as this one
        is, which is what clients have always done with it. A provider naming
        another type is the case to refuse: that token carries a protection
        this client does not implement, and presenting it as a bearer token
        is both a failure and, for a bound token, the one thing RFC 9449,
        Section 7.2 has the resource server reject.

        Raises:
            AuthenticationError: When the provider issued a token of another
                type than the one this client presents.
        """
        token_type = token_response.get("token_type")
        if token_type is None or token_type == "":
            return
        if not isinstance(token_type, str) or token_type.casefold() != _TOKEN_TYPE.casefold():
            raise AuthenticationError(
                f'The OIDC provider issued an access token of the "{token_type}" type, '
                "which this client cannot use: it presents bearer tokens "
                "(RFC 6749, Section 7.1).",
            )

    @override
    def prepare_token_request(
        self,
        url: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        """Return the options unchanged: a bearer token asks for nothing at the token endpoint.

        Args:
            url: The URL the request is about to be made to.
            options: The request options the request is about to be made with.

        Returns:
            The same request options.
        """
        del url
        return options

    @override
    def present_token(
        self,
        access_token: str,
        method: str,
        url: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        """Carry the token as the bearer credential of the request.

        Args:
            access_token: The token the token endpoint issued.
            method: The HTTP method the request is made with.
            url: The URL the request is about to be made to.
            options: The request options the request is about to be made with.

        Returns:
            The request options, carrying the token under "auth_bearer".
        """
        del method, url
        options["auth_bearer"] = access_token
        return options

    @override
    def on_response(self, response: HttpResponseInterface, url: str) -> bool:
        """Answer ``False``: a bearer token never asks for a second round.

        Args:
            response: The response the request came back with.
            url: The URL the request was made to.

        Returns:
            ``False``, always — the response is read as it is.
        """
        del response, url
        return False
