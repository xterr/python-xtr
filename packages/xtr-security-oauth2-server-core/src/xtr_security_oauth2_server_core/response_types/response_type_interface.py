"""What a grant hands what it issued to, and what turns that into an answer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )

__all__ = ["ResponseTypeInterface"]


@runtime_checkable
class ResponseTypeInterface(Protocol):
    """Turns what a grant issued into the answer a client reads.

    A grant never writes a response. It works out what the request has earned —
    an access token, sometimes a refresh token beside it — sets that here, and
    hands this object back. Whoever is answering the request then asks for the
    HTTP answer. That split is what lets one deployment hand out a plain bearer
    document and another hand out one carrying an identity token, without a
    single grant knowing the difference.

    The encryption key is set because a response type may have to seal state of
    its own: the refresh token a client receives is an encrypted payload naming
    the access token it belongs to, and the response type is what builds it.

    An implementation is handed a fresh response to build on rather than
    building one itself, so whoever is answering decides what the answer starts
    out as — a status, a header it always sets — and the response type only
    adds what it has to say.
    """

    def set_access_token(self, access_token: AccessTokenEntityInterface) -> None:
        """Carry ``access_token`` in the answer."""
        ...

    def set_refresh_token(self, refresh_token: RefreshTokenEntityInterface) -> None:
        """Carry ``refresh_token`` in the answer, beside the access token."""
        ...

    def set_encryption_key(self, key: str, key_type: Literal["plain", "key"]) -> None:
        """Take the key this response type seals its own payloads with.

        Args:
            key: A password when ``key_type`` is ``plain``, or the base64url of
                the key's bytes when it is ``key``.
            key_type: Which of the two ``key`` is.
        """
        ...

    async def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        """Build the answer this response type has to make, on top of ``response``.

        The status and the headers are set with the ``with_*`` methods, each of
        which answers a new response; the document goes into the body the
        response already has, which every copy of it shares.
        """
        ...
