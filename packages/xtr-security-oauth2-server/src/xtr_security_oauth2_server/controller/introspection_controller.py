"""The endpoint something asks what this server says about a token at."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.token_server import (  # noqa: TC002 -- container hydrates this constructor at runtime
    TokenServer,
)

from ._served_response import served

if TYPE_CHECKING:
    from xtr_http_kernel.bridge import Response
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["IntrospectionController"]


@final
class IntrospectionController:
    """Says whether a token is live, and what it carries.

    An access token this server mints is a signed document, so a resource
    server normally reads it without asking anybody. This endpoint is for the
    cases where it cannot: a resource server that holds no key, one that will
    not parse a token itself, or one that needs to know whether a token has
    been withdrawn since it was signed.

    A token that is unreadable, expired, withdrawn or issued to somebody else
    is all answered the same way — not live — and nothing more is said about
    it, so the endpoint cannot be used to learn what an arbitrary string is.

    Off unless a deployment turns it on, and ``404`` until it does. It answers
    questions about tokens issued to *other* clients, which is a thing a
    deployment should decide to expose rather than discover it had.
    """

    __slots__ = ("_enabled", "_server")

    def __init__(self, server: TokenServer, enabled: bool) -> None:
        """Answer about tokens through ``server``, or answer ``404`` unless ``enabled``."""
        self._server = server
        self._enabled = enabled

    async def index_action(
        self,
        request: ServerRequestInterface,
        response: Response,
    ) -> Response:
        """Answer what this server says about the token ``request`` names."""
        if not self._enabled:
            return response.with_status(HTTPStatus.NOT_FOUND)
        try:
            answered = await self._server.respond_to_token_introspection_request(
                request,
                response,
            )
        except OAuthServerError as error:
            answered = error.generate_http_response(response)

        return served(answered)

    @override
    def __repr__(self) -> str:
        """Name the type and whether the endpoint is enabled, which is configuration."""
        return f"{type(self).__name__}(enabled={self._enabled!r})"
