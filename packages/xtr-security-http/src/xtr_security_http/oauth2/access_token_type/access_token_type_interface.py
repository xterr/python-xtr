"""The type of access token a client asks for, and knows how to use."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import HttpResponseInterface

__all__ = ["AccessTokenTypeInterface"]


@runtime_checkable
class AccessTokenTypeInterface(Protocol):
    """The type of access token a client asks for, and knows how to use.

    RFC 6749, Section 7.1: "The client MUST NOT use an access token if it does
    not understand the token type." The type is therefore not a detail of one
    request but a property of the client, which decides three things at once:
    what the provider must answer in the "token_type" of the access-token
    response (Section 5.1), what a request presenting the token looks like, and
    what the client has to prove along the way.

    One implementation per type, so that the client asks the type rather than
    asking which type it is: :class:`BearerTokenType` for the bearer token of
    RFC 6750, which is presented as it is. A type added later is a class
    added, and nothing that uses a token has to learn its name.

    """

    def get_token_type(self) -> str:
        """Return the "token_type" this type understands.

        The value is case-insensitive, and this is the spelling the
        specification writes.
        """
        ...

    def check_token_response(self, token_response: Mapping[str, object]) -> None:
        """Check what the token endpoint answered before any of it is used.

        A token of another type is one this client cannot present, and one
        whose type carries a protection this client asked for is one it must
        not silently do without.

        Args:
            token_response: The members of the access-token response.

        Raises:
            AuthenticationError: When the response holds no token this type
                can use.
        """
        ...

    def prepare_token_request(
        self,
        url: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        """Return the options of a request made to the authorization server itself.

        No access token exists yet at the token endpoint, which does not mean
        there is nothing to prove: this is where a type binding the token to a
        key signs for it.

        Args:
            url: The URL the request is about to be made to.
            options: The request options the request is about to be made
                with, carrying the token request body under the "body" key.

        Returns:
            The final request options.
        """
        ...

    def present_token(
        self,
        access_token: str,
        method: str,
        url: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        """Return the options of a request presenting the access token to a protected resource.

        Args:
            access_token: The token the token endpoint issued.
            method: The HTTP method the request is made with.
            url: The URL the request is about to be made to.
            options: The request options the request is about to be made
                with.

        Returns:
            The final request options.
        """
        ...

    def on_response(self, response: HttpResponseInterface, url: str) -> bool:
        """Read what ``response`` named and say whether the request is to be made again.

        A server may answer a first request with what the next one has to
        carry — a DPoP nonce being the one case today, RFC 9449, Section 8.
        Returning ``True`` asks the caller to build and send the request once
        more; returning ``False`` leaves the response to be read as it is,
        including when it is an error.

        Args:
            response: The response the request came back with.
            url: The URL the request was made to.

        Returns:
            Whether the caller is to build and send the request again.
        """
        ...
