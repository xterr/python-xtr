"""A refresh token buys a new pair, and is spent doing it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from .abstract_grant import DEFAULT_REFRESH_TOKEN_TTL, AbstractGrant

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import timedelta

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["RefreshTokenGrant"]

#: What separates the scopes a token was granted, when they are handed back to
#: the scope reader as the parameter a request would have carried.
_SCOPE_DELIMITER = " "


@final
@dataclass(frozen=True, slots=True)
class _SpentRefreshToken:
    """What a refresh token's sealed payload turned out to say.

    The payload is read into this once, at the edge, so the rest of the grant
    works on names and numbers that are what they claim to be rather than on a
    mapping of anything. A payload missing either identifier never becomes one
    of these.
    """

    identifier: str
    access_token_id: str
    scopes: tuple[str, ...]
    user_identifier: str | None


def _identity(payload: Mapping[str, object], name: str) -> str | None:
    """Read ``name`` as a resource owner's identifier, however it was recorded.

    A deployment whose users are numbered seals a number, and a token is named
    by a string, so a number read back is the name it stands for.
    """
    value = payload.get(name)
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or not isinstance(value, int):
        return None

    return str(value)


@final
class RefreshTokenGrant(AbstractGrant):
    """Exchanges a refresh token for a new access token, and usually a new refresh token.

    An access token is short-lived on purpose; a refresh token is how a client
    goes on acting for a resource owner without asking them again. Everything
    the new token is made of comes out of the old one's sealed payload, so no
    state is read back from storage but the two revocation flags.

    Redeeming one spends it. The access token it was issued beside is always
    revoked, and the refresh token itself is revoked too unless a deployment
    turned that off — and the revocation is what decides the request, not a
    check before it: the repository reports whether *this* call revoked the
    token, so of two requests racing to refresh the same token exactly one is
    answered and the other is told its token is invalid. A token that reads
    valid and then cannot be revoked has been used by somebody else.

    A request may ask for fewer scopes than the old token carried, never more.
    """

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> None:
        """Mint and revoke refresh tokens through ``refresh_token_repository``."""
        super().__init__(dispatcher, clock)
        self.set_refresh_token_repository(refresh_token_repository)
        self.set_refresh_token_ttl(DEFAULT_REFRESH_TOKEN_TTL)

    @override
    def get_identifier(self) -> str:
        """Return ``refresh_token``, the name a request asks for this grant by."""
        return "refresh_token"

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Spend the refresh token in ``request`` and hand out a new pair.

        Raises:
            OAuthServerError: When the client cannot be authenticated, the
                refresh token cannot be read, is not this client's, has
                expired, was revoked, or was spent by another request; and when
                the request asks for a scope the old token did not carry.
        """
        client = await self.validate_client(request)
        spent = await self.validate_old_refresh_token(request, client.get_identifier())
        scopes = await self.validate_scopes(
            self.get_request_parameter(
                "scope",
                request,
                _SCOPE_DELIMITER.join(spent.scopes),
            ),
        )
        for scope in scopes:
            if scope.get_identifier() not in spent.scopes:
                raise OAuthServerError.invalid_scope(scope.get_identifier())
        granted = await self._scope_repository_or_fail().finalize_scopes(
            scopes,
            self.get_identifier(),
            client,
            spent.user_identifier,
        )
        await self._access_token_repository_or_fail().revoke_access_token(spent.access_token_id)
        if self._revoke_refresh_tokens:
            repository = self._refresh_token_repository_or_fail()
            if not await repository.revoke_refresh_token(spent.identifier):
                raise OAuthServerError.invalid_refresh_token(
                    "The refresh token has already been used",
                )
        await self._issue_tokens(
            request,
            response_type,
            access_token_ttl,
            client,
            spent.user_identifier,
            granted,
        )

        return response_type

    async def validate_old_refresh_token(
        self,
        request: ServerRequestInterface,
        client_id: str,
    ) -> _SpentRefreshToken:
        """Read the refresh token in ``request`` back, and say it may be spent.

        Raises:
            OAuthServerError: When the request carries none, this server did
                not seal it, it names another client, it has expired, it is
                malformed, or it was already revoked.
        """
        sealed = self.get_request_parameter("refresh_token", request)
        if sealed is None:
            raise OAuthServerError.invalid_request("refresh_token")
        payload = await self.validate_encrypted_refresh_token(request, sealed, client_id)

        return self._spent(payload)

    def _spent(self, payload: Mapping[str, object]) -> _SpentRefreshToken:
        """Read ``payload`` into the four things spending a refresh token takes.

        Raises:
            OAuthServerError: When the payload names no refresh token or no
                access token to revoke beside it, which a payload this server
                sealed always does.
        """
        identifier = self._payload_text(payload, "refresh_token_id")
        access_token_id = self._payload_text(payload, "access_token_id")
        if identifier is None or access_token_id is None:
            raise OAuthServerError.invalid_refresh_token("Token is malformed")

        return _SpentRefreshToken(
            identifier,
            access_token_id,
            self._payload_names(payload, "scopes"),
            _identity(payload, "user_id"),
        )
