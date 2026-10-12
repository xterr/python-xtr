"""A device with no keyboard polls while its owner approves it elsewhere."""

from __future__ import annotations

import secrets
from functools import partial
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.request_event import RequestEvent
from xtr_security_oauth2_server.response_types.device_code_response import DeviceCodeResponse

from .abstract_grant import DEFAULT_REFRESH_TOKEN_TTL, AbstractGrant

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime, timedelta

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.device_code_entity_interface import (
        DeviceCodeEntityInterface,
    )
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface
    from xtr_security_oauth2_server.repositories.device_code_repository_interface import (
        DeviceCodeRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["USER_CODE_ALPHABET", "DeviceCodeGrant"]

#: What a user code is drawn from. Twenty consonants, no vowels and no digits:
#: nothing here reads as a word by accident, and nothing is mistaken for
#: anything else when it is read off a screen and typed on a phone.
USER_CODE_ALPHABET: Final[str] = "BCDFGHJKLMNPQRSTVWXZ"

#: How many characters a user code is. Eight of this alphabet is about 34 bits,
#: which is what RFC 8628 section 6.1 asks for — on the understanding that
#: whoever serves the verification page limits how often it may be guessed at.
_USER_CODE_LENGTH: Final[int] = 8


@final
class DeviceCodeGrant(AbstractGrant):
    """Issues two codes, and hands out a token once the second one is approved.

    For a device that cannot show a browser: a television, a command-line tool,
    something with a screen and no keyboard. It asks for two codes — one it
    keeps and polls this server with, and a short one it shows its owner, who
    types it into the verification page on a device that does have a keyboard.
    When they approve it there, the device's next poll is answered with a token.

    Polling is the whole difficulty of the flow. A device that polls faster than
    it was told to is answered ``slow_down``, and that answer is not free of
    consequence: the poll is recorded *before* the refusal is raised, so the
    next one is judged against it. A device that cannot be slowed down this way
    would otherwise poll in a tight loop for as long as its owner takes to
    reach a phone.

    A device code is single use. It is revoked as soon as it is exchanged, so a
    code read off a device that has already been authorized buys nothing.
    """

    def __init__(  # noqa: PLR0913, PLR0917 -- one wiring of one flow, not seven choices
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        device_code_repository: DeviceCodeRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
        device_code_ttl: timedelta,
        verification_uri: str,
        retry_interval: int = 5,
    ) -> None:
        """Issue codes lasting ``device_code_ttl``, to be approved at ``verification_uri``."""
        super().__init__(dispatcher, clock)
        self.set_refresh_token_repository(refresh_token_repository)
        self.set_refresh_token_ttl(DEFAULT_REFRESH_TOKEN_TTL)
        self._device_code_repository: DeviceCodeRepositoryInterface = device_code_repository
        self._device_code_ttl: timedelta = device_code_ttl
        self._verification_uri: str = verification_uri
        self._retry_interval: int = retry_interval
        self._include_verification_uri_complete: bool = False
        self._interval_visibility: bool = False

    @override
    def get_identifier(self) -> str:
        """Return the URN a request asks for this grant by."""
        return "urn:ietf:params:oauth:grant-type:device_code"

    def set_verification_uri(self, verification_uri: str) -> None:
        """Send resource owners to ``verification_uri`` to type their user code in."""
        self._verification_uri = verification_uri

    @override
    def set_interval_visibility(self, interval_visibility: bool) -> None:
        """Choose whether a device is told how long to wait between polls."""
        self._interval_visibility = interval_visibility

    @override
    def get_interval_visibility(self) -> bool:
        """Tell whether a device is told how long to wait between polls."""
        return self._interval_visibility

    @override
    def set_include_verification_uri_complete(
        self,
        include_verification_uri_complete: bool,
    ) -> None:
        """Choose whether a device is sent the verification URI with its code in it."""
        self._include_verification_uri_complete = include_verification_uri_complete

    @override
    def can_respond_to_device_authorization_request(self, request: ServerRequestInterface) -> bool:
        """Answer yes: this is the grant device authorization requests are for."""
        del request

        return True

    @override
    async def respond_to_device_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> DeviceCodeResponse:
        """Issue the pair of codes the device polls with and its owner types in.

        The client is not made to authenticate here, as RFC 8628 section 3.1
        has it: the flow exists for clients that cannot keep a secret, and the
        pair of codes is worth nothing until a resource owner approves it.

        Raises:
            OAuthServerError: When the request names no client or an unknown
                one, the client may not use this grant, or a scope is unknown.
        """
        basic_user, _ = self.get_basic_auth_credentials(request)
        client_id = self.get_request_parameter("client_id", request, basic_user)
        if client_id is None:
            raise OAuthServerError.invalid_request("client_id")
        client = await self.get_client_entity_or_fail(client_id, request)
        scopes = await self.validate_scopes(
            self.get_request_parameter("scope", request, self._default_scope_or_fail()),
        )
        device_code = await self.issue_device_code(
            self._device_code_ttl,
            client,
            self._verification_uri,
            scopes,
        )
        response = DeviceCodeResponse(self._clock)
        if self._include_verification_uri_complete:
            response.include_verification_uri_complete()
        if self._interval_visibility:
            response.include_interval()
        response.set_device_code_entity(device_code)

        return response

    @override
    async def complete_device_authorization_request(
        self,
        device_code: str,
        user_id: str,
        user_approved: bool,
    ) -> None:
        """Record what the resource owner decided about ``device_code``.

        Called by whatever serves the verification page, once it knows who is
        looking at it and what they chose.

        Raises:
            OAuthServerError: When no such code is stored, or no resource owner
                was named — a code approved on behalf of nobody would be
                exchanged for a token acting for nobody.
        """
        stored = await self._device_code_repository.get_device_code_entity_by_device_code(
            device_code,
        )
        if stored is None:
            raise OAuthServerError.invalid_request("device_code", "Device code does not exist")
        if user_id == "":
            raise OAuthServerError.invalid_request("user_id", "User ID is required")
        stored.set_user_identifier(user_id)
        stored.set_user_approved(user_approved)
        await self._device_code_repository.persist_device_code(stored)

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Answer a polling device: wait, slow down, refused, or here is your token.

        Raises:
            OAuthServerError: With ``authorization_pending`` while nobody has
                decided, ``slow_down`` when the device polled too soon,
                ``access_denied`` when its owner refused, and the usual
                refusals when the code or the client is not what it claims.
        """
        client = await self.validate_client(request)
        device_code = await self.validate_device_code(request, client)
        owner = device_code.get_user_identifier()
        if owner is None:
            await self._record_poll(device_code)

            raise OAuthServerError.authorization_pending()
        if not device_code.get_user_approved():
            raise OAuthServerError.access_denied()
        granted = await self._scope_repository_or_fail().finalize_scopes(
            device_code.get_scopes(),
            self.get_identifier(),
            client,
            owner,
        )
        await self._issue_tokens(request, response_type, access_token_ttl, client, owner, granted)
        await self._device_code_repository.revoke_device_code(device_code.get_identifier())

        return response_type

    async def validate_device_code(
        self,
        request: ServerRequestInterface,
        client: ClientEntityInterface,
    ) -> DeviceCodeEntityInterface:
        """Return the stored code ``request`` polls with.

        A code nobody issued is announced as a failed authentication: the
        device flow has no client secret, so a stream of unknown codes is the
        shape a brute-force attempt takes here.

        Raises:
            OAuthServerError: When the request carries no code, no such code
                is stored, the code has expired or been spent, or it was
                issued to another client.
        """
        polled_with = self.get_request_parameter("device_code", request)
        if polled_with is None:
            raise OAuthServerError.invalid_request("device_code")
        stored = await self._device_code_repository.get_device_code_entity_by_device_code(
            polled_with,
        )
        if stored is None:
            await self._announce(RequestEvent.USER_AUTHENTICATION_FAILED, request)

            raise OAuthServerError.invalid_grant()
        if self._clock.now().timestamp() > stored.get_expiry_date_time().timestamp():
            raise OAuthServerError.expired_token("device_code")
        if await self._device_code_repository.is_device_code_revoked(polled_with):
            raise OAuthServerError.invalid_request("device_code", "Device code has been revoked")
        if stored.get_client().get_identifier() != client.get_identifier():
            raise OAuthServerError.invalid_request(
                "device_code",
                "Device code was not issued to this client",
            )

        return stored

    async def issue_device_code(
        self,
        device_code_ttl: timedelta,
        client: ClientEntityInterface,
        verification_uri: str,
        scopes: Sequence[ScopeEntityInterface] = (),
    ) -> DeviceCodeEntityInterface:
        """Mint and store the pair of codes for ``client``.

        Both codes are minted together on every attempt, so a collision on the
        device code mints a new user code too rather than reusing one that may
        already be on somebody's screen.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When no free
                identifier was found.
        """
        device_code = await self._device_code_repository.get_new_device_code()
        device_code.set_expiry_date_time(self._clock.now() + device_code_ttl)
        device_code.set_client(client)
        device_code.set_verification_uri(verification_uri)
        device_code.set_interval(self._retry_interval)
        for scope in scopes:
            device_code.add_scope(scope)
        await self._store_under_a_free_identifier(
            partial(self._name_device_code, device_code),
            partial(self._device_code_repository.persist_device_code, device_code),
        )

        return device_code

    def generate_user_code(self, length: int = _USER_CODE_LENGTH) -> str:
        """Return a user code of ``length`` characters for somebody to type in."""
        return "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(length))

    def _name_device_code(self, device_code: DeviceCodeEntityInterface, identifier: str) -> None:
        """Name ``device_code`` and give it a fresh user code to go with it."""
        device_code.set_identifier(identifier)
        device_code.set_user_code(self.generate_user_code())

    async def _record_poll(self, device_code: DeviceCodeEntityInterface) -> None:
        """Record this poll, and refuse it if it came too soon after the last.

        The recording happens whatever the answer is, which is the point: a
        device told to slow down has to be judged against the poll that was
        refused, or it would be told to slow down for ever.

        Raises:
            OAuthServerError: ``slow_down`` when the last poll was less than
                the interval ago.
        """
        too_soon = self._polled_too_soon(device_code.get_last_polled_at())
        device_code.set_last_polled_at(self._clock.now())
        await self._device_code_repository.persist_device_code(device_code)
        if too_soon:
            raise OAuthServerError.slow_down()

    def _polled_too_soon(self, last_polled_at: datetime | None) -> bool:
        """Tell whether the previous poll was less than the interval ago."""
        if last_polled_at is None:
            return False

        return last_polled_at.timestamp() + self._retry_interval > self._clock.now().timestamp()
