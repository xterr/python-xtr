"""Withdrawing the token a client hands over, and saying no more than that it is done."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from typing_extensions import override

from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from .abstract_token_handler import AbstractTokenHandler

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )

    from .validated_token import ValidatedToken

__all__ = ["TokenRevocationHandler"]

#: The two kinds of token this server issues and withdraws.
_ACCESS_TOKEN: Final[str] = "access_token"  # noqa: S105 -- a token kind, not a secret
_REFRESH_TOKEN: Final[str] = "refresh_token"  # noqa: S105 -- a token kind, not a secret


class TokenRevocationHandler(AbstractTokenHandler):
    """Answers RFC 7009: the client is done with a token, so this server is too.

    The answer is the same whether a token was withdrawn or nothing was
    recognised at all (RFC 7009, Section 2.2): a client is told its token is
    gone, never whether it existed.

    A refresh token takes the access token it was issued beside with it
    (RFC 7009, Section 2.1): a client that asked to be rid of its refresh
    token did not mean to keep spending the access token it came with.

    An access token is withdrawn only if it names the client that is asking,
    either as the client it was issued to or as the audience it is addressed
    to. Another client's token is recognised and left standing — and still
    answered the same way, because a refusal would be an oracle telling a
    client that somebody else's token is real.
    """

    @override
    async def respond_to_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Withdraw the token ``request`` names, and answer that it is done.

        Raises:
            OAuthServerError: ``invalid_client`` when the client cannot be
                authenticated, ``invalid_request`` when the request names no
                token, and ``unsupported_token_type`` when the token was read
                as a kind this server does not withdraw.
        """
        client = await self.validate_client(request)
        token = await self.validate_token(request, client)
        if token is not None:
            await self._revoke(token, client)

        return response.with_status(200).with_header("cache-control", "no-store")

    async def _revoke(self, token: ValidatedToken, client: ClientEntityInterface) -> None:
        """Withdraw what ``token`` turned out to be, as far as ``client`` may.

        Raises:
            OAuthServerError: ``unsupported_token_type`` when the token was
                read as a third kind, which only a deployment that reads
                tokens of its own can produce.
        """
        data = token.token_data
        if token.token_type == _REFRESH_TOKEN:
            await self._revoke_refresh_token(data)

            return
        if token.token_type == _ACCESS_TOKEN:
            if self._issued_to(data, client.get_identifier()):
                await self._revoke_access_token(data, "jti")

            return

        raise OAuthServerError.unsupported_token_type()

    async def _revoke_refresh_token(self, data: Mapping[str, object]) -> None:
        """Withdraw the refresh token ``data`` names, and the access token with it."""
        identifier = self._payload_text(data, "refresh_token_id")
        if identifier is not None:
            _ = await self._refresh_token_repository_or_fail().revoke_refresh_token(identifier)
        await self._revoke_access_token(data, "access_token_id")

    async def _revoke_access_token(self, data: Mapping[str, object], name: str) -> None:
        """Withdraw the access token ``data`` names under ``name``, if it names one."""
        identifier = self._payload_text(data, name)
        if identifier is None:
            return
        await self._access_token_repository_or_fail().revoke_access_token(identifier)

    def _issued_to(self, data: Mapping[str, object], client_id: str) -> bool:
        """Tell whether the access token ``data`` describes belongs to ``client_id``."""
        if self._payload_text(data, "client_id") == client_id:
            return True

        return client_id in self._payload_names(data, "aud")
