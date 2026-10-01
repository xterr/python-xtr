"""The authenticator that proves a caller by a self-issued token."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeGuard, cast, final

from typing_extensions import override
from xtr_security_core.exception import AuthenticationError, UserNotFoundError
from xtr_security_core.user.attributes_based_user_provider_interface import (
    AttributesBasedUserProviderInterface,
)
from xtr_security_core.user.chain_user_provider import ChainUserProvider
from xtr_security_http import AbstractAuthenticator, SelfValidatingPassport, UserBadge
from xtr_security_http.entry_point.authentication_entry_point_interface import (
    AuthenticationEntryPointInterface,
)

from xtr_security_jwt.event.jwt_authenticated_event import JwtAuthenticatedEvent
from xtr_security_jwt.event.jwt_expired_event import JwtExpiredEvent
from xtr_security_jwt.event.jwt_invalid_event import JwtInvalidEvent
from xtr_security_jwt.event.jwt_not_found_event import JwtNotFoundEvent
from xtr_security_jwt.events import Events
from xtr_security_jwt.exception.expired_token_error import ExpiredTokenError
from xtr_security_jwt.exception.invalid_payload_error import InvalidPayloadError
from xtr_security_jwt.exception.invalid_token_error import InvalidTokenError
from xtr_security_jwt.exception.jwt_decode_failure_error import JwtDecodeFailureError
from xtr_security_jwt.exception.missing_token_error import MissingTokenError
from xtr_security_jwt.response.jwt_authentication_failure_response import (
    JwtAuthenticationFailureResponse,
)
from xtr_security_jwt.security.authenticator.token.jwt_post_authentication_token import (
    JwtPostAuthenticationToken,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface
    from xtr_security_http.authenticator.passport.passport import Passport

    from xtr_security_jwt.services.jwt_token_manager_interface import JwtTokenManagerInterface
    from xtr_security_jwt.token_extractor.token_extractor_interface import TokenExtractorInterface

__all__ = ["JwtAuthenticator"]

#: The passport attribute the verified payload is stashed under.
_PAYLOAD_ATTRIBUTE: str = "payload"

#: The passport and token attribute the raw compact token is stashed under.
_TOKEN_ATTRIBUTE: str = "token"  # noqa: S105 -- an attribute name, not a secret


@final
class JwtAuthenticator(AbstractAuthenticator, AuthenticationEntryPointInterface):
    """Proves a caller by a self-issued token, and challenges when one is absent or bad.

    The token extractor reads a token out of the request; the token manager
    verifies it into its claims; the claim naming the user becomes a user badge
    whose loader resolves the user through the firewall's provider. The passport
    is self-validating — the signature already proved the caller — so no
    credentials are checked.

    As the firewall's entry point it answers a request that carried no token with
    a ``401`` naming that the token was not found, dispatching the not-found event;
    a token that was refused draws the expired or the invalid event, and the
    response either carries.
    """

    __slots__ = ("_event_dispatcher", "_jwt_manager", "_token_extractor", "_user_provider")

    def __init__(
        self,
        jwt_manager: JwtTokenManagerInterface,
        event_dispatcher: EventDispatcherInterface,
        token_extractor: TokenExtractorInterface,
        user_provider: UserProviderInterface,
    ) -> None:
        """Verify tokens with ``jwt_manager`` and load users through ``user_provider``."""
        self._jwt_manager = jwt_manager
        self._event_dispatcher = event_dispatcher
        self._token_extractor = token_extractor
        self._user_provider = user_provider

    @override
    def supports(self, request: Request) -> bool | None:
        """Handle the request only when the extractor finds a token in it."""
        return self._token_extractor.extract(request) is not None

    @override
    async def authenticate(self, request: Request) -> SelfValidatingPassport:
        """Verify the token and build a self-validating passport for its user.

        Raises:
            ExpiredTokenError: When the token has expired.
            InvalidTokenError: When the token cannot be read or verified.
            InvalidPayloadError: When the payload lacks the user-id claim.
        """
        token = self._token_extractor.extract(request)
        if token is None:  # pragma: no cover — supports() guards this
            raise InvalidTokenError("No token was found in the request.")
        payload = await self._parse(token)
        id_claim = self._jwt_manager.get_user_id_claim()
        if id_claim not in payload:
            raise InvalidPayloadError(id_claim)
        identity = str(payload[id_claim])

        async def load(identifier: str) -> UserInterface:
            return await self._load_user(payload, identifier)

        passport = SelfValidatingPassport(UserBadge(identity, load))
        passport.set_attribute(_PAYLOAD_ATTRIBUTE, payload)
        passport.set_attribute(_TOKEN_ATTRIBUTE, token)
        return passport

    async def _parse(self, token: str) -> Mapping[str, object]:
        """Verify a token, mapping a decode failure to an authentication error.

        Raises:
            ExpiredTokenError: When the token has expired.
            InvalidTokenError: When the token cannot be read or verified.
        """
        try:
            return await self._jwt_manager.parse(token)
        except JwtDecodeFailureError as error:
            if error.get_reason() == JwtDecodeFailureError.EXPIRED_TOKEN:
                raise ExpiredTokenError from error
            raise InvalidTokenError from error

    async def _load_user(
        self,
        payload: Mapping[str, object],
        identity: str,
    ) -> UserInterface:
        """Load the user ``identity`` names, passing the payload where a provider reads it.

        Raises:
            UserNotFoundError: When no provider in a chain could load the user.
        """
        provider = self._user_provider
        if _is_attributes_based(provider):
            return await provider.load_user_by_identifier(identity, payload)
        if isinstance(provider, ChainUserProvider):
            return await self._load_from_chain(provider, payload, identity)
        return await provider.load_user_by_identifier(identity)

    async def _load_from_chain(
        self,
        provider: ChainUserProvider,
        payload: Mapping[str, object],
        identity: str,
    ) -> UserInterface:
        """Try each provider in a chain, passing the payload to those that read it.

        Raises:
            UserNotFoundError: When every provider in the chain refused.
        """
        for member in provider.get_providers():
            try:
                if _is_attributes_based(member):
                    return await member.load_user_by_identifier(identity, payload)
                return await member.load_user_by_identifier(identity)
            except AuthenticationError:
                continue
        raise UserNotFoundError(identity)

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build the token, then announce it so a listener may inspect or reject it.

        Args:
            passport: The self-validating passport authentication settled on.
            firewall_name: The firewall the token belongs to.
        """
        user = passport.get_user_badge().get_loaded_user()
        raw = str(passport.get_attribute(_TOKEN_ATTRIBUTE))
        token = JwtPostAuthenticationToken(user, firewall_name, tuple(user.get_roles()), raw)
        payload = _as_mapping(passport.get_attribute(_PAYLOAD_ATTRIBUTE))
        event = JwtAuthenticatedEvent(dict(payload), token)
        _ = await self._event_dispatcher.dispatch(event, Events.JWT_AUTHENTICATED)
        return token

    @override
    async def on_authentication_success(
        self,
        request: Request,
        token: TokenInterface,
        firewall_name: str,
    ) -> Response | None:
        """Answer nothing: the success response is built by the firewall's handler."""
        del request, token, firewall_name
        return None

    @override
    async def on_authentication_failure(
        self,
        request: Request,
        error: AuthenticationError,
    ) -> Response | None:
        """Answer a refused token with a ``401``, drawing the expired or invalid event."""
        response = JwtAuthenticationFailureResponse(error.get_message_key())
        if isinstance(error, ExpiredTokenError):
            expired = JwtExpiredEvent(error, response, request)
            _ = await self._event_dispatcher.dispatch(expired, Events.JWT_EXPIRED)
            return expired.get_response()
        invalid = JwtInvalidEvent(error, response, request)
        _ = await self._event_dispatcher.dispatch(invalid, Events.JWT_INVALID)
        return invalid.get_response()

    @override
    async def start(
        self,
        request: Request,
        error: AuthenticationError | None = None,
    ) -> Response:
        """Answer a request that carried no token with a ``401`` naming it missing.

        The error that drew the challenge, when one is given, is kept as the cause
        of the missing-token error, so the reason the firewall fell through to the
        entry point is not lost.
        """
        missing = MissingTokenError("JWT Token not found")
        if error is not None:
            missing.__cause__ = error
        response = JwtAuthenticationFailureResponse(missing.get_message_key())
        event = JwtNotFoundEvent(missing, response, request)
        _ = await self._event_dispatcher.dispatch(event, Events.JWT_NOT_FOUND)
        return event.get_response()


def _is_attributes_based(
    provider: UserProviderInterface,
) -> TypeGuard[AttributesBasedUserProviderInterface]:
    """Tell whether ``provider`` reads a payload, by explicit inheritance.

    A structural check cannot tell the two provider protocols apart — the
    attributes-based one only widens ``load_user_by_identifier`` — so the class's
    own bases decide, and a plain provider is never handed the payload.
    """
    return AttributesBasedUserProviderInterface in type(provider).__mro__


def _as_mapping(value: object) -> Mapping[str, object]:
    """Narrow a stashed payload attribute back to a mapping.

    Raises:
        InvalidTokenError: When the stashed payload is not a mapping, named for
            its real cause rather than borrowing the missing-claim error, and
            rather than letting a malformed payload pass as an empty one.
    """
    if isinstance(value, dict):
        return cast("Mapping[str, object]", value)
    raise InvalidTokenError("The verified token payload is not a mapping.")
