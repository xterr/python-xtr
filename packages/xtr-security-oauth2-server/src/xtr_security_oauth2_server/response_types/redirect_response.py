"""The answer that sends the browser back to where the client is waiting."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError

from .abstract_response_type import AbstractResponseType

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

__all__ = ["RedirectResponse"]

_NO_REDIRECT_URI = (
    "This redirect response names nowhere to go; the grant completing the authorization "
    "request sets it with set_redirect_uri() before the answer is built."
)


@final
class RedirectResponse(AbstractResponseType):
    """Answers a redirect, and nothing else.

    This is what an authorization request is answered with once the resource
    owner has decided: the whole result — an authorization code, or in the
    implicit flow the access token itself — is already in the URI the grant
    built, so the answer is the status and the header that carry the browser
    there.

    Nothing else goes into it on purpose. A body would not be read, and a
    content type would describe a document that is not there.
    """

    #: Where the browser is being sent; absent until the grant says where.
    _redirect_uri: str | None = None

    def set_redirect_uri(self, redirect_uri: str) -> None:
        """Send the browser on to ``redirect_uri``."""
        self._redirect_uri = redirect_uri

    @override
    def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        """Answer a redirect to the URI this response was given.

        Raises:
            InvalidArgumentError: When no URI was set, which would otherwise
                answer a redirect to nowhere.
        """
        if self._redirect_uri is None:
            raise InvalidArgumentError(_NO_REDIRECT_URI)

        return response.with_status(302).with_header("Location", self._redirect_uri)
