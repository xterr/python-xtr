"""The endpoint a client asks for a token it holds to be withdrawn at."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.token_server import (  # noqa: TC001 -- container hydrates this constructor at runtime
    TokenServer,
)

from ._served_response import served

if TYPE_CHECKING:
    from xtr_http_kernel.bridge import Response
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["RevocationController"]


@final
class RevocationController:
    """Withdraws the token a client is done with, and says so.

    A client that signs a person out, or notices a token has leaked, should be
    able to make it stop working before it expires rather than waiting out its
    lifetime. That is this endpoint: the client authenticates as it does at the
    token endpoint, names a token it was itself issued, and the server
    withdraws it.

    Withdrawing a refresh token withdraws the access token issued beside it, so
    a client that gives up one credential does not keep the other working by
    accident.

    A token this server cannot read, or one issued to somebody else, is
    answered the same way as one just withdrawn. Saying which of the three it
    was would turn the endpoint into a way of asking whether an arbitrary
    string is a live token.

    It answers ``404`` when the deployment has not enabled it, for the same
    reason the device-code endpoint does.
    """

    __slots__ = ("_enabled", "_server")

    def __init__(self, server: TokenServer, enabled: bool) -> None:
        """Withdraw tokens through ``server``, or answer ``404`` unless ``enabled``."""
        self._server = server
        self._enabled = enabled

    async def index_action(
        self,
        request: ServerRequestInterface,
        response: Response,
    ) -> Response:
        """Withdraw the token ``request`` names, and answer that it is done."""
        if not self._enabled:
            return response.with_status(HTTPStatus.NOT_FOUND)
        try:
            answered = await self._server.respond_to_token_revocation_request(request, response)
        except OAuthServerError as error:
            answered = error.generate_http_response(response)

        return served(answered)

    @override
    def __repr__(self) -> str:
        """Name the type and whether the endpoint is enabled, which is configuration."""
        return f"{type(self).__name__}(enabled={self._enabled!r})"
