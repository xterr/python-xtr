"""Answering what this server will say about the token a client hands over."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_oauth2_server.response_types.introspection_response import IntrospectionResponse

from .abstract_token_handler import AbstractTokenHandler

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server.response_types.introspection_response_type_interface import (
        IntrospectionResponseTypeInterface,
    )

__all__ = ["TokenIntrospectionHandler"]


class TokenIntrospectionHandler(AbstractTokenHandler):
    """Answers RFC 7662: whether a token is live, and what it says.

    A token this handler will not speak for — unknown, expired, withdrawn, or
    a refresh token sealed for another client — is answered ``active: false``
    and nothing else, because anything more would let a client ask about
    tokens it does not hold.

    The document is handed out per request as a shallow copy of the one this
    handler was given, so two requests being answered at the same time cannot
    read each other's token: whatever is filled in lands on a copy nobody else
    holds, while the services the copy shares with its original — anything a
    deployment injected into its own document — are the same objects.
    """

    def __init__(self, dispatcher: EventDispatcherInterface, clock: ClockInterface) -> None:
        """Announce through ``dispatcher``, and read every instant from ``clock``."""
        super().__init__(dispatcher, clock)
        self._response_type: IntrospectionResponseTypeInterface | None = None

    def set_response_type(self, response_type: IntrospectionResponseTypeInterface) -> None:
        """Take what the answers this handler gives are built by."""
        self._response_type = response_type

    @override
    async def respond_to_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Answer what this server will say about the token ``request`` names.

        Raises:
            OAuthServerError: ``invalid_client`` when the client cannot be
                authenticated, and ``invalid_request`` when the request names
                no token.
        """
        client = await self.validate_client(request)
        token = await self.validate_token(request, client)
        response_type = self._response_type_for_request()
        if token is None:
            response_type.set_active(False)
        else:
            response_type.set_active(True)
            response_type.set_token_type(token.token_type)
            response_type.set_token_data(token.token_data)

        return response_type.generate_http_response(response)

    def _response_type_for_request(self) -> IntrospectionResponseTypeInterface:
        """Return a document for this request alone, nobody else's to write to."""
        given = self._response_type

        return IntrospectionResponse() if given is None else copy.copy(given)
