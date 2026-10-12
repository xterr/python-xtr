"""What the authorization server announces when a refresh token has been issued."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_oauth2_server_core.request_event import RequestEvent

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )

__all__ = ["RequestRefreshTokenEvent"]


@final
class RequestRefreshTokenEvent(RequestEvent):
    """A refresh token has been issued, and this is it.

    Announced under :data:`RequestEvent.REFRESH_TOKEN_ISSUED` whenever a grant
    issues one, so an application can record the long-lived credential it
    handed out and the access token it belongs to.

    The token arrives as the entity, not as the encrypted string a client
    receives: the listener reads what it needs from it and the credential
    itself never has to be passed around.
    """

    __slots__ = ("_refresh_token",)

    def __init__(
        self,
        name: str,
        request: ServerRequestInterface,
        refresh_token: RefreshTokenEntityInterface,
    ) -> None:
        """Announce ``refresh_token``, issued while answering ``request``."""
        super().__init__(name, request)
        self._refresh_token: RefreshTokenEntityInterface = refresh_token

    def get_refresh_token(self) -> RefreshTokenEntityInterface:
        """Return the refresh token that was issued."""
        return self._refresh_token
