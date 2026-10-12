"""What both endpoints about a token share: reading the token a client handed over."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Final

from typing_extensions import override

from xtr_security_oauth2_server_core.abstract_handler import AbstractHandler
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from .token_handler_interface import TokenHandlerInterface
from .validated_token import ValidatedToken

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server_core.authorization_validators.bearer_token_validator_interface import (  # noqa: E501 -- one dotted path, nothing to break
        BearerTokenValidatorInterface,
    )
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )

__all__ = ["AbstractTokenHandler"]

#: The two kinds of token this server issues, as a client names them in
#: ``token_type_hint`` and as a reading names what it accepted.
_ACCESS_TOKEN: Final[str] = "access_token"  # noqa: S105 -- a token kind, not a secret
_REFRESH_TOKEN: Final[str] = "refresh_token"  # noqa: S105 -- a token kind, not a secret


class AbstractTokenHandler(AbstractHandler, TokenHandlerInterface, ABC):
    """Reads the token a request names, as either of the kinds this server issues.

    A client handing a token to one of these endpoints knows what it holds but
    not what this server calls it, so it says which kind it thinks it is and
    that is taken as a hint only: the hinted reading is tried first and the
    other after it, which is what RFC 7009 Section 2.1 and RFC 7662
    Section 2.1 ask of a server that accepts both.

    Every way a reading can fail answers the same way: nothing. A token that
    was never issued here, that expired, that was withdrawn, or that belongs
    to another client is one this handler will not speak for, and the two
    endpoints turn that into the one answer each of them gives — a withdrawal
    that says it succeeded, a question that says nothing is live. Telling them
    apart would make either endpoint an oracle a client could ask about tokens
    it does not hold.

    Only the request naming no token at all is refused, because that is the
    client's mistake rather than a token this server cannot speak for.

    A refresh token is read against the asking client, because the payload
    names the client it was sealed for. An access token is not: it is read for
    what it says, and what each endpoint does about the client it names is the
    endpoint's own business — a withdrawal leaves another client's token
    standing, while a question answers what the token says.
    """

    def __init__(self, dispatcher: EventDispatcherInterface, clock: ClockInterface) -> None:
        """Announce through ``dispatcher``, and read every instant from ``clock``."""
        super().__init__(dispatcher, clock)
        self._bearer_token_validator: BearerTokenValidatorInterface | None = None

    @abstractmethod
    @override
    async def respond_to_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Answer ``request`` on top of ``response``."""
        ...

    @override
    def set_bearer_token_validator(
        self,
        bearer_token_validator: BearerTokenValidatorInterface,
    ) -> None:
        """Take what the access tokens this handler is handed are read by.

        It is the same reading a resource server does, so a token this server
        would refuse at a protected resource is one this handler will not
        speak for either.
        """
        self._bearer_token_validator = bearer_token_validator

    async def validate_token(
        self,
        request: ServerRequestInterface,
        client: ClientEntityInterface,
    ) -> ValidatedToken | None:
        """Return what the token ``request`` names turned out to be, or ``None``.

        Raises:
            OAuthServerError: ``invalid_request`` when the request names no
                token.
        """
        token = self.get_request_parameter("token", request)
        if token is None:
            raise OAuthServerError.invalid_request("token")
        hint = self.get_request_parameter("token_type_hint", request, _ACCESS_TOKEN)
        # The hint only decides which reading is tried first: a client that
        # guesses wrong costs a second reading, not a refusal.
        if hint == _REFRESH_TOKEN:
            sealed = await self._validate_refresh_token(request, token, client)
            if sealed is not None:
                return sealed

            return await self._validate_access_token(request, token)
        signed = await self._validate_access_token(request, token)
        if signed is not None:
            return signed

        return await self._validate_refresh_token(request, token, client)

    async def _validate_refresh_token(
        self,
        request: ServerRequestInterface,
        refresh_token: str,
        client: ClientEntityInterface,
    ) -> ValidatedToken | None:
        """Read ``refresh_token`` as a refresh token sealed for ``client``, or answer ``None``."""
        try:
            payload = await self.validate_encrypted_refresh_token(
                request,
                refresh_token,
                client.get_identifier(),
            )
        except OAuthServerError:
            return None

        return ValidatedToken(_REFRESH_TOKEN, payload)

    async def _validate_access_token(
        self,
        request: ServerRequestInterface,
        access_token: str,
    ) -> ValidatedToken | None:
        """Read ``access_token`` as an access token this server signed, or answer ``None``."""
        validator = self._bearer_token_validator_or_fail()
        try:
            claims = await validator.validate_bearer_token(request, access_token)
        except OAuthServerError:
            return None

        return ValidatedToken(_ACCESS_TOKEN, claims)

    def _bearer_token_validator_or_fail(self) -> BearerTokenValidatorInterface:
        """Return what the access tokens this handler is handed are read by."""
        return self._wired(self._bearer_token_validator, "set_bearer_token_validator")
