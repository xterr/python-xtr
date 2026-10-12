"""Everything every grant does the same way: authenticate, validate, issue."""

from __future__ import annotations

import secrets
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING, Final, cast

from typing_extensions import override

# Every grant inherits this class's constructor, and a deployment may register
# one as a class for the grant pass to collect, so the two names it reads have
# to be resolvable at runtime.
from xtr_clock import (
    ClockInterface,  # noqa: TC002 -- container hydrates this constructor at runtime
)
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- container hydrates this constructor at runtime
    EventDispatcherInterface,
)

from xtr_security_oauth2_server.abstract_handler import AbstractHandler
from xtr_security_oauth2_server.exception import UniqueTokenIdentifierConstraintViolationError
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.redirect_uri_validators.redirect_uri_validator import (
    RedirectUriValidator,
)
from xtr_security_oauth2_server.request_access_token_event import RequestAccessTokenEvent
from xtr_security_oauth2_server.request_event import RequestEvent
from xtr_security_oauth2_server.request_refresh_token_event import RequestRefreshTokenEvent

from .grant_type_interface import GrantTypeInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server.entities.access_token_signer import AccessTokenSigner
    from xtr_security_oauth2_server.entities.auth_code_entity_interface import (
        AuthCodeEntityInterface,
    )
    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface
    from xtr_security_oauth2_server.repositories.auth_code_repository_interface import (
        AuthCodeRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.scope_repository_interface import (
        ScopeRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.user_repository_interface import (
        UserRepositoryInterface,
    )
    from xtr_security_oauth2_server.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server.response_types.device_code_response import DeviceCodeResponse
    from xtr_security_oauth2_server.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["DEFAULT_REFRESH_TOKEN_TTL", "AbstractGrant"]

#: What separates the scopes a request asks for, in a request and in a token.
_SCOPE_DELIMITER: Final[str] = " "

#: How many identifiers a grant mints before giving up on finding a free one.
#: Ten collisions on forty random bytes is not bad luck, it is a broken
#: generator or a repository reporting a collision it did not have.
_MAX_RANDOM_TOKEN_GENERATION_ATTEMPTS: Final[int] = 10

#: How many random bytes a token identifier is made of, hex-encoded into twice
#: as many characters.
_IDENTIFIER_BYTES: Final[int] = 40

#: How long a refresh token lasts unless a deployment says otherwise. Each
#: grant that issues one sets it at construction, as the server then overrides
#: it from configuration.
DEFAULT_REFRESH_TOKEN_TTL: Final[timedelta] = timedelta(days=30)


def _split_scopes(scopes: str) -> tuple[str, ...]:
    """Split a scope parameter into the names it asks for, empties dropped."""
    return tuple(name for name in scopes.strip().split(_SCOPE_DELIMITER) if name != "")


class AbstractGrant(AbstractHandler, GrantTypeInterface, ABC):
    """What every grant is built out of: client authentication, scopes, issuing.

    A grant subclasses this and writes the one thing that makes it a grant —
    what a client has to present, and what that earns. Everything around that
    is the same whichever flow it is: turning a scope string into scopes,
    minting tokens under a free identifier and announcing what was issued live
    here, and everything a request about a token the client already holds does
    the same way — reading the parameters, reading the credentials, proving
    which client is asking, opening a refresh token this server sealed — lives
    in :class:`~xtr_security_oauth2_server.abstract_handler.AbstractHandler`
    underneath.

    Nothing here has a default standing in for wiring. The repositories, the
    signing key, the encryption key and the default scope arrive through the
    setters the authorization server calls when it enables a grant, and a grant
    asked to work before that says which setter was never called. A grant that
    quietly fell back to a key or a repository of its own choosing would issue
    tokens nobody could verify.

    The event dispatcher and the clock are constructor arguments rather than
    setters, because neither is optional and neither has a sensible default: a
    grant that could not announce what it issued would leave an application no
    way to audit it, and a grant reading the system clock could not be tested
    for anything that expires.
    """

    def __init__(self, dispatcher: EventDispatcherInterface, clock: ClockInterface) -> None:
        """Announce through ``dispatcher``, and read every instant from ``clock``."""
        super().__init__(dispatcher, clock)
        self._scope_repository: ScopeRepositoryInterface | None = None
        self._auth_code_repository: AuthCodeRepositoryInterface | None = None
        self._user_repository: UserRepositoryInterface | None = None
        self._refresh_token_ttl: timedelta | None = None
        self._private_key: AccessTokenSigner | None = None
        self._default_scope: str | None = None
        self._revoke_refresh_tokens: bool = True

    @abstractmethod
    @override
    def get_identifier(self) -> str:
        """Return the name a request asks for this grant by."""
        ...

    @abstractmethod
    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Answer a token request, setting what it earned on ``response_type``."""
        ...

    @override
    def set_scope_repository(self, scope_repository: ScopeRepositoryInterface) -> None:
        """Take the repository scopes are read from and finalised through."""
        self._scope_repository = scope_repository

    def set_auth_code_repository(self, auth_code_repository: AuthCodeRepositoryInterface) -> None:
        """Take the repository authorization codes are minted and stored through."""
        self._auth_code_repository = auth_code_repository

    def set_user_repository(self, user_repository: UserRepositoryInterface) -> None:
        """Take the repository a resource owner's own credentials are checked against."""
        self._user_repository = user_repository

    @override
    def set_default_scope(self, scope: str) -> None:
        """Take the scopes a request asking for none is read as asking for."""
        self._default_scope = scope

    @override
    def set_private_key(self, private_key: AccessTokenSigner) -> None:
        """Take what the access tokens this grant issues sign themselves with."""
        self._private_key = private_key

    @override
    def set_refresh_token_ttl(self, refresh_token_ttl: timedelta) -> None:
        """Take how long the refresh tokens this grant issues last."""
        self._refresh_token_ttl = refresh_token_ttl

    @override
    def revoke_refresh_tokens(self, will_revoke: bool) -> None:
        """Choose whether redeeming a refresh token revokes it."""
        self._revoke_refresh_tokens = will_revoke

    @override
    def can_respond_to_access_token_request(self, request: ServerRequestInterface) -> bool:
        """Tell whether the request asks for this grant by name.

        The name is read as it was sent rather than through
        :meth:`get_request_parameter`, because this only decides which grant is
        offered the request: a body that is not a form, or a ``grant_type``
        that is not text, is a request no grant claims rather than one refused
        here.
        """
        body = request.get_parsed_body()
        if not isinstance(body, Mapping):
            return False

        # The cast says what narrowing cannot: a mapping of anything is a
        # mapping of objects, and the one name read is compared as it was sent.
        named = cast("Mapping[str, object]", body).get("grant_type")

        return named == self.get_identifier()

    @override
    def can_respond_to_authorization_request(self, request: ServerRequestInterface) -> bool:
        """Answer no: only the grants that send a browser somewhere say otherwise."""
        del request

        return False

    @override
    async def validate_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> AuthorizationRequestInterface:
        """Say that this grant answers no authorization request.

        Raises:
            InvalidArgumentError: Always. Reaching here means the server asked
                a grant to do something it said it could not.
        """
        del request

        raise InvalidArgumentError(
            f"The `{self.get_identifier()}` grant answers no authorization request; ask "
            "can_respond_to_authorization_request() before handing it one.",
        )

    @override
    async def complete_authorization_request(
        self,
        request: ServerRequestInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> ResponseTypeInterface:
        """Say that this grant completes no authorization request.

        Raises:
            InvalidArgumentError: Always, for the same reason as
                :meth:`validate_authorization_request`.
        """
        del request, authorization_request

        raise InvalidArgumentError(
            f"The `{self.get_identifier()}` grant completes no authorization request; only a "
            "grant that validated one can complete it.",
        )

    @override
    def can_respond_to_device_authorization_request(self, request: ServerRequestInterface) -> bool:
        """Answer no: only the device flow says otherwise."""
        del request

        return False

    @override
    async def respond_to_device_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> DeviceCodeResponse:
        """Say that this grant answers no device authorization request.

        Raises:
            InvalidArgumentError: Always.
        """
        del request

        raise InvalidArgumentError(
            f"The `{self.get_identifier()}` grant answers no device authorization request; ask "
            "can_respond_to_device_authorization_request() before handing it one.",
        )

    @override
    async def complete_device_authorization_request(
        self,
        device_code: str,
        user_id: str,
        user_approved: bool,
    ) -> None:
        """Say that this grant completes no device authorization request.

        Raises:
            InvalidArgumentError: Always.
        """
        del device_code, user_id, user_approved

        raise InvalidArgumentError(
            f"The `{self.get_identifier()}` grant completes no device authorization request; "
            "only the device flow issues the codes one is completed with.",
        )

    @override
    def set_interval_visibility(self, interval_visibility: bool) -> None:
        """Say that this grant has no polling interval to show.

        Raises:
            InvalidArgumentError: Always. Only a device polls, so only the
                device flow has an interval, and setting one here would be a
                setting nobody reads.
        """
        del interval_visibility

        raise InvalidArgumentError(
            f"The `{self.get_identifier()}` grant has no polling interval to show; only the "
            "device flow is polled.",
        )

    @override
    def get_interval_visibility(self) -> bool:
        """Answer no: only the device flow has an interval to show."""
        return False

    @override
    def set_include_verification_uri_complete(
        self,
        include_verification_uri_complete: bool,
    ) -> None:
        """Say that this grant issues no verification URI.

        Raises:
            InvalidArgumentError: Always, for the same reason as
                :meth:`set_interval_visibility`.
        """
        del include_verification_uri_complete

        raise InvalidArgumentError(
            f"The `{self.get_identifier()}` grant sends nobody to a verification_uri_complete; "
            "only the device flow issues a user code to type in.",
        )

    @override
    async def get_client_entity_or_fail(
        self,
        client_id: str,
        request: ServerRequestInterface,
    ) -> ClientEntityInterface:
        """Return the client registered as ``client_id``, if it may use this grant.

        A client that is not registered and one that is not allowed this grant
        are both refusals, and the two are told apart because only the first is
        a failure to authenticate worth announcing.

        Raises:
            OAuthServerError: When no such client is registered, or it may not
                use this grant.
        """
        client = await super().get_client_entity_or_fail(client_id, request)
        if not self.supports_grant_type(client, self.get_identifier()):
            raise OAuthServerError.unauthorized_client()

        return client

    def supports_grant_type(self, client: ClientEntityInterface, grant_type: str) -> bool:
        """Tell whether ``client`` is allowed to use ``grant_type``.

        Every client answers the question — the shipped client trait says yes
        to everything — so this asks rather than probing for the method, and a
        deployment that restricts its clients overrides one method on its own
        entity.
        """
        return client.supports_grant_type(grant_type)

    async def validate_redirect_uri(
        self,
        redirect_uri: str,
        client: ClientEntityInterface,
        request: ServerRequestInterface,
    ) -> None:
        """Refuse unless ``redirect_uri`` is one ``client`` registered.

        The refusal is a failed client authentication rather than a bad
        parameter, and it is never delivered to the URI that was asked for:
        answering an unregistered URI at all is the open redirect this check
        exists to prevent.

        Raises:
            OAuthServerError: When the URI is not one of the registered ones.
        """
        if RedirectUriValidator(client.get_redirect_uri()).validate_redirect_uri(redirect_uri):
            return
        await self._announce(RequestEvent.CLIENT_AUTHENTICATION_FAILED, request)

        raise OAuthServerError.invalid_client(request)

    async def validate_scopes(
        self,
        scopes: str | Sequence[str] | None,
        redirect_uri: str | None = None,
    ) -> Sequence[ScopeEntityInterface]:
        """Return the scopes ``scopes`` names, every one of them known here.

        Args:
            scopes: A scope parameter as a request carries it, the names
                already split, or nothing at all.
            redirect_uri: Where a refusal is to be delivered, when the request
                naming the scopes was one that redirects.

        Raises:
            OAuthServerError: When a name is one this deployment does not know.
        """
        if scopes is None:
            names: Sequence[str] = ()
        elif isinstance(scopes, str):
            names = _split_scopes(scopes)
        else:
            names = scopes
        repository = self._scope_repository_or_fail()
        found: list[ScopeEntityInterface] = []
        for name in names:
            scope = await repository.get_scope_entity_by_identifier(name)
            if scope is None:
                raise OAuthServerError.invalid_scope(name, redirect_uri)
            found.append(scope)

        return tuple(found)

    async def issue_access_token(
        self,
        access_token_ttl: timedelta,
        client: ClientEntityInterface,
        user_identifier: str | None,
        scopes: Sequence[ScopeEntityInterface] = (),
    ) -> AccessTokenEntityInterface:
        """Mint, sign and store an access token for ``client``.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When no free
                identifier was found.
        """
        repository = self._access_token_repository_or_fail()
        access_token = await repository.get_new_token(client, scopes, user_identifier)
        access_token.set_expiry_date_time(self._clock.now() + access_token_ttl)
        access_token.set_private_key(self._wired(self._private_key, "set_private_key"))
        await self._store_under_a_free_identifier(
            access_token.set_identifier,
            partial(repository.persist_new_access_token, access_token),
        )

        return access_token

    async def issue_auth_code(
        self,
        auth_code_ttl: timedelta,
        client: ClientEntityInterface,
        user_identifier: str,
        redirect_uri: str | None,
        scopes: Sequence[ScopeEntityInterface] = (),
    ) -> AuthCodeEntityInterface:
        """Mint and store an authorization code for ``client`` and ``user_identifier``.

        A code issued for a request that named no redirect URI carries none, so
        the token request may not name one either.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When no free
                identifier was found.
        """
        repository = self._auth_code_repository_or_fail()
        auth_code = await repository.get_new_auth_code()
        auth_code.set_expiry_date_time(self._clock.now() + auth_code_ttl)
        auth_code.set_client(client)
        auth_code.set_user_identifier(user_identifier)
        if redirect_uri is not None:
            auth_code.set_redirect_uri(redirect_uri)
        for scope in scopes:
            auth_code.add_scope(scope)
        await self._store_under_a_free_identifier(
            auth_code.set_identifier,
            partial(repository.persist_new_auth_code, auth_code),
        )

        return auth_code

    async def issue_refresh_token(
        self,
        access_token: AccessTokenEntityInterface,
    ) -> RefreshTokenEntityInterface | None:
        """Mint and store a refresh token beside ``access_token``, when there is to be one.

        Answers ``None`` in the two cases that are not errors: a client not
        registered for the refresh grant, and a deployment whose repository
        mints none.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When no free
                identifier was found.
        """
        if not self.supports_grant_type(access_token.get_client(), "refresh_token"):
            return None
        repository = self._refresh_token_repository_or_fail()
        refresh_token = await repository.get_new_refresh_token()
        if refresh_token is None:
            return None
        ttl = self._wired(self._refresh_token_ttl, "set_refresh_token_ttl")
        refresh_token.set_expiry_date_time(self._clock.now() + ttl)
        refresh_token.set_access_token(access_token)
        await self._store_under_a_free_identifier(
            refresh_token.set_identifier,
            partial(repository.persist_new_refresh_token, refresh_token),
        )

        return refresh_token

    def generate_unique_identifier(self, length: int = _IDENTIFIER_BYTES) -> str:
        """Return ``length`` random bytes as hexadecimal, twice as many characters.

        Raises:
            OAuthServerError: When asked for an identifier of no length, which
                would name every token the same.
        """
        if length < 1:
            raise OAuthServerError.server_error("Could not generate a random string")

        return secrets.token_hex(length)

    async def _store_under_a_free_identifier(
        self,
        name: Callable[[str], None],
        store: Callable[[], Awaitable[None]],
    ) -> None:
        """Name a token and store it, trying another name while the last was taken.

        The two halves arrive as callables because what is named and what is
        stored differ per token — a device code is given a user code at the
        same time — while the retry around them does not.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When every attempt
                found its identifier taken.
        """
        for attempt in range(_MAX_RANDOM_TOKEN_GENERATION_ATTEMPTS):
            name(self.generate_unique_identifier())
            try:
                await store()
            except UniqueTokenIdentifierConstraintViolationError:
                if attempt == _MAX_RANDOM_TOKEN_GENERATION_ATTEMPTS - 1:
                    raise
            else:
                return

    async def _issue_tokens(  # noqa: PLR0913, PLR0917 -- one step of a flow, not six choices
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
        client: ClientEntityInterface,
        user_identifier: str | None,
        scopes: Sequence[ScopeEntityInterface],
    ) -> None:
        """Issue what a token request earned, announce it, and set it on the answer.

        Every grant that ends at the token endpoint with a refresh token does
        exactly this, in this order: the access token is announced and set
        before the refresh token exists, so a listener recording what was
        issued sees them in the order they were issued.
        """
        access_token = await self.issue_access_token(
            access_token_ttl,
            client,
            user_identifier,
            scopes,
        )
        await self._announce_access_token(request, access_token)
        response_type.set_access_token(access_token)
        refresh_token = await self.issue_refresh_token(access_token)
        if refresh_token is None:
            return
        event = RequestRefreshTokenEvent(
            RequestEvent.REFRESH_TOKEN_ISSUED,
            request,
            refresh_token,
        )
        _ = await self._dispatcher.dispatch(event, RequestEvent.REFRESH_TOKEN_ISSUED)
        response_type.set_refresh_token(refresh_token)

    async def _announce_access_token(
        self,
        request: ServerRequestInterface,
        access_token: AccessTokenEntityInterface,
    ) -> None:
        """Say that ``access_token`` was issued while answering ``request``."""
        event = RequestAccessTokenEvent(RequestEvent.ACCESS_TOKEN_ISSUED, request, access_token)
        _ = await self._dispatcher.dispatch(event, RequestEvent.ACCESS_TOKEN_ISSUED)

    def _default_scope_or_fail(self) -> str:
        """Return the scopes a request asking for none is read as asking for."""
        return self._wired(self._default_scope, "set_default_scope")

    def _scope_repository_or_fail(self) -> ScopeRepositoryInterface:
        """Return the repository scopes are read from and finalised through."""
        return self._wired(self._scope_repository, "set_scope_repository")

    def _auth_code_repository_or_fail(self) -> AuthCodeRepositoryInterface:
        """Return the repository authorization codes are minted and stored through."""
        return self._wired(self._auth_code_repository, "set_auth_code_repository")

    def _user_repository_or_fail(self) -> UserRepositoryInterface:
        """Return the repository a resource owner's credentials are checked against."""
        return self._wired(self._user_repository, "set_user_repository")

    @override
    def __repr__(self) -> str:
        """Name the grant by its identifier, and nothing it holds.

        A grant holds the signing key, the encryption key and every repository
        the server reaches storage through; none of it belongs in a log line or
        a traceback.
        """
        return f"<{type(self).__name__} {self.get_identifier()}>"
