"""The endpoint a client exchanges what it holds for a token at."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- container hydrates this constructor at runtime
    EventDispatcherInterface,
)
from xtr_security_oauth2_server_core.authorization_server import (  # noqa: TC002 -- container hydrates this constructor at runtime
    AuthorizationServer,
)
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from xtr_security_oauth2_server.event.token_request_resolve_event import TokenRequestResolveEvent
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

from ._served_response import served

if TYPE_CHECKING:
    from xtr_http_kernel.bridge import Response
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["TokenController"]


@final
class TokenController:
    """Hands whichever enabled grant can answer the request its answer to give.

    Every flow ends here except the one that hands a token straight to the
    browser: a code is redeemed here, a refresh token is spent here, a client
    authenticates as itself here, a device polls here. Which of them is
    answering is not this endpoint's business — the server offers the request
    to each enabled grant until one claims it.

    The answer is announced before it is sent, refusals included, so a
    deployment with a field of its own to add to the token response adds it in
    a listener rather than by replacing this endpoint. A refusal is announced
    for the same reason: an answer is an answer, and a deployment counting
    failed exchanges wants to see them.
    """

    __slots__ = ("_dispatcher", "_server")

    def __init__(
        self,
        server: AuthorizationServer,
        dispatcher: EventDispatcherInterface,
    ) -> None:
        """Answer token requests on ``server``, announcing each answer on ``dispatcher``."""
        self._server = server
        self._dispatcher = dispatcher

    async def index_action(
        self,
        request: ServerRequestInterface,
        response: Response,
    ) -> Response:
        """Answer ``request`` with what a grant issued, or with its refusal."""
        try:
            answered = await self._server.respond_to_access_token_request(request, response)
        except OAuthServerError as error:
            answered = error.generate_http_response(response)
        event = TokenRequestResolveEvent(answered)
        _ = await self._dispatcher.dispatch(event, OAuth2Events.TOKEN_REQUEST_RESOLVE)

        return served(event.get_response())

    @override
    def __repr__(self) -> str:
        """Name the type; what it holds says nothing a reader needs."""
        return f"{type(self).__name__}()"
