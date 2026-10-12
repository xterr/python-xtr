"""What the authorization server announces when an access token has been issued."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_oauth2_server_core.request_event import RequestEvent

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )

__all__ = ["RequestAccessTokenEvent"]


@final
class RequestAccessTokenEvent(RequestEvent):
    """An access token has been issued, and this is it.

    Announced under :data:`RequestEvent.ACCESS_TOKEN_ISSUED` by every grant
    that issues one, so an application can record what it handed out — who
    asked, for which client, with which scopes and until when — without the
    grants knowing anything about that.

    The token arrives as the entity, not as the string a client receives: the
    listener reads what it needs from it and the signed form never has to be
    passed around.
    """

    __slots__ = ("_access_token",)

    def __init__(
        self,
        name: str,
        request: ServerRequestInterface,
        access_token: AccessTokenEntityInterface,
    ) -> None:
        """Announce ``access_token``, issued while answering ``request``."""
        super().__init__(name, request)
        self._access_token: AccessTokenEntityInterface = access_token

    def get_access_token(self) -> AccessTokenEntityInterface:
        """Return the access token that was issued."""
        return self._access_token
