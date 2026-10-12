"""What every handler of a client's request shares: reading it, and proving the client."""

# The only edge from this module into the ``grant`` package is a deliberate
# function-local import in ``_validate_client`` (deferred precisely to avoid a
# runtime cycle — naming the grant contract at module scope would be one).
# basedpyright follows that deferred edge and reports a module cycle, so the
# check is turned off here rather than undoing the deferral the import exists for.
# pyright: reportImportCycles=false

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, TypeVar, cast

from xtr_security_oauth2_server_core._repeated_parameter import refuse_if_repeated
from xtr_security_oauth2_server_core.crypt_trait import CryptTrait
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.exception.oauth2_error import OAuth2Error
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.request_event import RequestEvent

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )
    from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (
        AccessTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
        ClientRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )

__all__ = ["AbstractHandler"]

#: How long the HTTP Basic scheme's name and separator are, so the rest of the
#: header is the credentials.
_BASIC_PREFIX_LENGTH: Final[int] = 6

_T = TypeVar("_T")


def _parse_param(
    parameter: str,
    source: Mapping[str, object],
    default: str | None,
) -> str | None:
    """Read ``parameter`` out of ``source``, falling back to ``default``.

    Surrounding space is dropped and an empty value counts as absent, because
    a client that sends ``client_id=`` has named no client and should be told
    so rather than be looked up under the empty name.

    A name the request sent more than once is refused rather than read, the
    way :func:`~xtr_security_oauth2_server_core._repeated_parameter.refuse_if_repeated`
    describes.

    Every protocol parameter travels as text — a token request is a form, a
    query string is text — so a value that is anything else is a malformed
    request rather than something to coerce: a file posted under the name of a
    parameter, or a JSON number where an identifier belongs.

    Raises:
        OAuthServerError: ``invalid_request`` when the name was sent more than
            once, or is carried by something that is not text.
    """
    refuse_if_repeated(parameter, source)
    carried = source.get(parameter, "")
    if not isinstance(carried, str):
        raise OAuthServerError.invalid_request(parameter)
    value = carried.strip()
    if value == "" and default is not None:
        value = default.strip()

    return value if value != "" else None


def _parsed_body(request: ServerRequestInterface) -> Mapping[str, object]:
    """Return the parameters in the body of ``request``, none when there are none.

    A body is parsed into whatever its content type says it carries, so what
    comes back need not be named parameters at all — a JSON array, or nothing
    for a request with no body. Either reads as carrying no parameter, which is
    what a protocol request that is not a form amounts to.
    """
    body = request.get_parsed_body()
    if not isinstance(body, Mapping):
        return {}

    # The cast says what narrowing cannot: a mapping of anything is a mapping
    # of objects, and every value is then asked whether it is text.
    return cast("Mapping[str, object]", body)


class AbstractHandler(CryptTrait):
    """What a grant and a token handler are both built out of.

    Two kinds of request reach this server carrying client credentials: the
    ones a flow answers, and the ones that are about a token the client
    already holds. Everything the two do the same way lives here — reading a
    parameter out of the request, reading the credentials out of the body or
    the Basic header, proving which client they name, and opening a refresh
    token this server sealed — so a flow and a handler cannot drift apart on
    any of it.

    Nothing here has a default standing in for wiring. The repositories and
    the encryption key arrive through the setters whoever owns the handler
    calls, and a handler asked to work before that says which setter was never
    called: one that quietly fell back to a repository of its own choosing
    would answer for storage nobody configured.

    The event dispatcher and the clock are constructor arguments rather than
    setters, because neither is optional and neither has a sensible default: a
    handler that could not announce a failed authentication would leave an
    application no way to watch for credential stuffing, and one reading the
    system clock could not be tested for anything that expires.
    """

    def __init__(self, dispatcher: EventDispatcherInterface, clock: ClockInterface) -> None:
        """Announce through ``dispatcher``, and read every instant from ``clock``."""
        self._dispatcher: EventDispatcherInterface = dispatcher
        self._clock: ClockInterface = clock
        self._client_repository: ClientRepositoryInterface | None = None
        self._access_token_repository: AccessTokenRepositoryInterface | None = None
        self._refresh_token_repository: RefreshTokenRepositoryInterface | None = None

    def set_client_repository(self, client_repository: ClientRepositoryInterface) -> None:
        """Take the repository registered clients are read from."""
        self._client_repository = client_repository

    def set_access_token_repository(
        self,
        access_token_repository: AccessTokenRepositoryInterface,
    ) -> None:
        """Take the repository access tokens are minted and stored through."""
        self._access_token_repository = access_token_repository

    def set_refresh_token_repository(
        self,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> None:
        """Take the repository refresh tokens are minted and stored through."""
        self._refresh_token_repository = refresh_token_repository

    async def validate_client(self, request: ServerRequestInterface) -> ClientEntityInterface:
        """Return the client ``request`` proved it is.

        A confidential client is made to present a secret before the repository
        is asked anything, so a request that forgot one is told what is missing
        rather than being counted as a failed authentication. A public client
        presents none and the repository decides whether that is allowed.

        The flow being used is named to the repository only by a handler that
        is a flow: a request about a token the client already holds belongs to
        no flow, so there is nothing to judge the client's registration
        against and the repository is told so.

        Raises:
            OAuthServerError: When no client is named, a confidential client
                sent no secret, or authentication failed.
        """
        client_id, client_secret = self.get_client_credentials(request)
        client = await self.get_client_entity_or_fail(client_id, request)
        if not client.is_confidential():
            return client
        if client_secret == "":
            raise OAuthServerError.invalid_request("client_secret")
        from xtr_security_oauth2_server_core.grant.grant_type_interface import (  # noqa: PLC0415 -- the grants are built on this class, so naming their contract at module scope would be a cycle
            GrantTypeInterface,
        )

        grant_type = self.get_identifier() if isinstance(self, GrantTypeInterface) else None
        repository = self._client_repository_or_fail()
        if not await repository.validate_client(client_id, client_secret, grant_type):
            await self._announce(RequestEvent.CLIENT_AUTHENTICATION_FAILED, request)

            raise OAuthServerError.invalid_client(request)

        return client

    async def get_client_entity_or_fail(
        self,
        client_id: str,
        request: ServerRequestInterface,
    ) -> ClientEntityInterface:
        """Return the client registered as ``client_id``.

        Unlike the repository this wraps, it never answers nothing: a request
        naming a client nobody registered is a failed authentication, and it is
        announced as one so a deployment watching for credential stuffing sees
        it.

        Raises:
            OAuthServerError: When no such client is registered.
        """
        repository = self._client_repository_or_fail()
        client = await repository.get_client_entity(client_id)
        if client is None:
            await self._announce(RequestEvent.CLIENT_AUTHENTICATION_FAILED, request)

            raise OAuthServerError.invalid_client(request)

        return client

    def get_client_credentials(self, request: ServerRequestInterface) -> tuple[str, str]:
        """Return the client identifier and secret the request carries.

        The body is read first and the header is only its default, so a client
        sending both is taken at the word of its body — which is what RFC 6749
        section 2.3.1 expects of a server that accepts either.

        Raises:
            OAuthServerError: When the request names no client at all.
        """
        basic_user, basic_password = self.get_basic_auth_credentials(request)
        client_id = self.get_request_parameter("client_id", request, basic_user)
        if client_id is None:
            raise OAuthServerError.invalid_request("client_id")
        client_secret = self.get_request_parameter("client_secret", request, basic_password)

        return (client_id, client_secret if client_secret is not None else "")

    def get_basic_auth_credentials(
        self,
        request: ServerRequestInterface,
    ) -> tuple[str | None, str | None]:
        """Return the client identifier and secret sent as HTTP Basic, or two ``None``.

        Every way the header can fail to carry a pair — another scheme, a body
        that is not base64 or not text, no colon, an empty name — answers the
        same pair of ``None``, because a header that does not carry credentials
        is not an attempt to authenticate and the request may still carry them
        in its body.
        """
        header = request.get_header_line("Authorization")
        if header[:_BASIC_PREFIX_LENGTH].lower() != "basic ":
            return (None, None)
        try:
            decoded = base64.b64decode(header[_BASIC_PREFIX_LENGTH:], validate=True).decode(
                "utf-8",
            )
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return (None, None)
        username, separator, password = decoded.partition(":")
        if separator == "" or username == "":
            return (None, None)

        return (username, password)

    def get_request_parameter(
        self,
        parameter: str,
        request: ServerRequestInterface,
        default: str | None = None,
    ) -> str | None:
        """Read ``parameter`` out of the request body, or ``default``, or ``None``.

        Raises:
            OAuthServerError: ``invalid_request`` when the body carries the
                name more than once, or as something other than text.
        """
        return _parse_param(parameter, _parsed_body(request), default)

    def get_query_string_parameter(
        self,
        parameter: str,
        request: ServerRequestInterface,
        default: str | None = None,
    ) -> str | None:
        """Read ``parameter`` out of the query string, or ``default``, or ``None``.

        Raises:
            OAuthServerError: ``invalid_request`` when the query carries the
                name more than once, or as something other than text.
        """
        return _parse_param(parameter, request.get_query_params(), default)

    def get_cookie_parameter(
        self,
        parameter: str,
        request: ServerRequestInterface,
        default: str | None = None,
    ) -> str | None:
        """Read ``parameter`` out of the cookies, or ``default``, or ``None``.

        No shipped flow reads a cookie: it is here because a deployment's own
        handler or grant may carry something of its own that way, and reading
        it should be the same one line as reading a form field.

        Raises:
            OAuthServerError: ``invalid_request`` when the cookie is carried
                as something other than text.
        """
        return _parse_param(parameter, request.get_cookie_params(), default)

    def get_server_parameter(
        self,
        parameter: str,
        request: ServerRequestInterface,
        default: str | None = None,
    ) -> str | None:
        """Read ``parameter`` out of the environment the request arrived in.

        The environment describes the connection rather than the protocol, so
        no shipped flow reads it either; a deployment that authenticates a
        client by something the server in front established — a verified
        certificate, say — reads it here.

        Raises:
            OAuthServerError: ``invalid_request`` when the environment carries
                the name as something other than text.
        """
        return _parse_param(parameter, request.get_server_params(), default)

    async def validate_encrypted_refresh_token(
        self,
        request: ServerRequestInterface,
        encrypted_refresh_token: str,
        client_id: str,
    ) -> Mapping[str, object]:
        """Open ``encrypted_refresh_token`` and return the payload it carries.

        The payload is only handed back once every reason to refuse it is gone:
        this server sealed it, it names ``client_id``, its window is still
        open, it names the token it is, and that token has not been revoked.

        Raises:
            OAuthServerError: When this server did not seal the token, it names
                another client, it has expired, it names no token, or it was
                revoked.
        """
        try:
            payload = self.decrypt(encrypted_refresh_token)
        except OAuth2Error as error:
            raise OAuthServerError.invalid_refresh_token(
                "Cannot decrypt the refresh token",
            ) from error
        if self._payload_text(payload, "client_id") != client_id:
            await self._announce(RequestEvent.REFRESH_TOKEN_CLIENT_FAILED, request)

            raise OAuthServerError.invalid_refresh_token("Token is not linked to client")
        expire_time = self._payload_whole_number(payload, "expire_time")
        if expire_time is None or expire_time < int(self._clock.now().timestamp()):
            raise OAuthServerError.invalid_refresh_token("Token has expired")
        identifier = self._payload_text(payload, "refresh_token_id")
        if identifier is None:
            raise OAuthServerError.invalid_refresh_token("Token is malformed")
        repository = self._refresh_token_repository_or_fail()
        if await repository.is_refresh_token_revoked(identifier):
            raise OAuthServerError.invalid_refresh_token("Token has been revoked")

        return payload

    @staticmethod
    def _wired(value: _T | None, setter: str) -> _T:
        """Return ``value``, or say which setter nobody called.

        Raises:
            InvalidArgumentError: When ``value`` is absent, which is a wiring
                mistake: whoever owns a handler calls every setter before the
                first request reaches it, so one missing a setter was never
                wired at all.
        """
        if value is None:
            raise InvalidArgumentError(
                f"This handler was used before {setter}() was called; whoever owns it calls "
                "that setter before the first request reaches it.",
            )

        return value

    @staticmethod
    def _payload_text(payload: Mapping[str, object], name: str) -> str | None:
        """Read ``name`` out of a sealed payload as text, or ``None``.

        A payload this server sealed is still read for what it is: one sealed
        by an older version of this server, or by a deployment that has since
        changed what it carries, opens cleanly and says something else.
        """
        value = payload.get(name)

        return value if isinstance(value, str) else None

    @staticmethod
    def _payload_whole_number(payload: Mapping[str, object], name: str) -> int | None:
        """Read ``name`` out of a sealed payload as a whole number, or ``None``.

        A boolean is refused although it is one in Python: an expiry of
        ``True`` is a payload saying something other than an instant.
        """
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            return None

        return value

    @staticmethod
    def _payload_names(payload: Mapping[str, object], name: str) -> tuple[str, ...]:
        """Read ``name`` out of a sealed payload as names, empty when there are none."""
        value = payload.get(name)
        if not isinstance(value, list):
            return ()

        # The cast says what narrowing cannot: a list of anything is a list of
        # objects, and every item is then asked what it is.
        return tuple(item for item in cast("list[object]", value) if isinstance(item, str))

    def _client_repository_or_fail(self) -> ClientRepositoryInterface:
        """Return the repository registered clients are read from."""
        return self._wired(self._client_repository, "set_client_repository")

    def _access_token_repository_or_fail(self) -> AccessTokenRepositoryInterface:
        """Return the repository access tokens are minted and stored through."""
        return self._wired(self._access_token_repository, "set_access_token_repository")

    def _refresh_token_repository_or_fail(self) -> RefreshTokenRepositoryInterface:
        """Return the repository refresh tokens are minted and stored through."""
        return self._wired(self._refresh_token_repository, "set_refresh_token_repository")

    async def _announce(self, name: str, request: ServerRequestInterface) -> None:
        """Say that ``name`` happened while ``request`` was being answered.

        The event carries the same name it is dispatched under, because a
        listener registers under that name and a mismatch would reach nobody
        and break nothing loudly.
        """
        _ = await self._dispatcher.dispatch(RequestEvent(name, request), name)
