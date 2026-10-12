"""The endpoint a device with no browser asks for its pair of codes at."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.authorization_server import (  # noqa: TC001 -- container hydrates this constructor at runtime
    AuthorizationServer,
)
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError

from ._served_response import served

if TYPE_CHECKING:
    from xtr_http_kernel.bridge import Response
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["DeviceCodeController"]


@final
class DeviceCodeController:
    """Issues the device code a device polls with and the user code a person types.

    The first half of the flow for something that cannot show a browser — a
    television, a command-line tool on a headless machine. The device asks
    here, is told a code to poll the token endpoint with, a short code for its
    owner to type somewhere else, and how long to wait between polls.

    It answers ``404`` when the deployment has not enabled the device flow.
    The route exists either way, because the router is built when the package
    is imported and cannot know a deployment's configuration; so "this server
    does not do that" is said in the answer rather than by the path being
    absent.
    """

    __slots__ = ("_enabled", "_server")

    def __init__(self, server: AuthorizationServer, enabled: bool) -> None:
        """Issue device codes on ``server``, or answer ``404`` unless ``enabled``."""
        self._server = server
        self._enabled = enabled

    async def index_action(
        self,
        request: ServerRequestInterface,
        response: Response,
    ) -> Response:
        """Answer ``request`` with a device code and a user code, or with a refusal."""
        if not self._enabled:
            return response.with_status(HTTPStatus.NOT_FOUND)
        try:
            answered = await self._server.respond_to_device_authorization_request(
                request,
                response,
            )
        except OAuthServerError as error:
            answered = error.generate_http_response(response)

        return served(answered)

    @override
    def __repr__(self) -> str:
        """Name the type and whether the flow is enabled, which is configuration."""
        return f"{type(self).__name__}(enabled={self._enabled!r})"
