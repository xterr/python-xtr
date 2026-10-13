"""A response type that keeps whatever a grant put on it.

A grant's whole output at the token endpoint is what it sets on the response
type it was handed, so the tests hand it this: a real implementation of the
contract that stores the access token, the refresh token and the encryption
key, and answers a plain 200 when asked for the HTTP answer.

Keeping it here rather than reaching for the shipped bearer response keeps the
grant tests about grants — what was issued, in what order, with which scopes —
and leaves the shape of the token document to the tests of the response type
that builds it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, final

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )

__all__ = ["RecordingResponseType"]


@final
class RecordingResponseType:
    """Stores what a grant set on it, and answers 200 when asked for a response."""

    def __init__(self) -> None:
        self.access_token: AccessTokenEntityInterface | None = None
        self.refresh_token: RefreshTokenEntityInterface | None = None
        self.encryption_key: tuple[str, Literal["plain", "key"]] | None = None

    def set_access_token(self, access_token: AccessTokenEntityInterface) -> None:
        """Keep the access token the grant issued."""
        self.access_token = access_token

    def set_refresh_token(self, refresh_token: RefreshTokenEntityInterface) -> None:
        """Keep the refresh token the grant issued."""
        self.refresh_token = refresh_token

    def set_encryption_key(self, key: str, key_type: Literal["plain", "key"]) -> None:
        """Keep the key this response type would seal its payloads with."""
        self.encryption_key = (key, key_type)

    async def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        """Answer 200, leaving the shape of a token document to the real thing."""
        return response.with_status(200)
