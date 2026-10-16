"""Reading an access token off a request, and challenging when there is none."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override
from xtr_security_http.authenticator.abstract_authenticator import AbstractAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import (
    SelfValidatingPassport,
)
from xtr_security_http.entry_point.authentication_entry_point_interface import (
    AuthenticationEntryPointInterface,
)
from xtr_security_oauth2_server_core.bearer_challenge import bearer_challenge
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from xtr_security_oauth2_server.security.authentication.token.oauth2_token import OAuth2Token
from xtr_security_oauth2_server.security.exception.oauth2_authentication_error import (
    OAuth2AuthenticationError,
)
from xtr_security_oauth2_server.security.exception.oauth2_authentication_failed_error import (
    OAuth2AuthenticationFailedError,
)
from xtr_security_oauth2_server.security.user.client_credentials_user import ClientCredentialsUser

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_http_message_contracts.factory import ResponseFactoryInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface
    from xtr_security_http.authenticator.passport.passport import Passport
    from xtr_security_oauth2_server_core.resource_server import ResourceServer

__all__ = ["OAuth2Authenticator"]

#: What a request has to start its ``Authorization`` header with to be one of
#: ours, written lowercase because the scheme name is compared that way.
_BEARER_PREFIX: Final = "bearer "

#: Where the resource server records what the token said, once it has read it.
_USER_ID_ATTRIBUTE: Final = "oauth_user_id"
_ACCESS_TOKEN_ID_ATTRIBUTE: Final = "oauth_access_token_id"  # noqa: S105 -- an attribute name, not a secret
_CLIENT_ID_ATTRIBUTE: Final = "oauth_client_id"
_SCOPES_ATTRIBUTE: Final = "oauth_scopes"

#: What this authenticator carries from reading the token to building the
#: token, on the passport.
_PASSPORT_ACCESS_TOKEN_ID: Final = "access_token_id"  # noqa: S105 -- an attribute name, not a secret
_PASSPORT_CLIENT_ID: Final = "oauth_client_id"
_PASSPORT_SCOPES: Final = "scopes"


@final
class OAuth2Authenticator(AbstractAuthenticator, AuthenticationEntryPointInterface):
    """Proves a caller by the access token it presented, and challenges when it did not.

    The whole resource-server side of a deployment. A request arrives carrying
    a bearer token; the resource server reads it — signature, issuer, audience,
    expiry, withdrawal — and records who it was issued to and what it may do.
    This turns that into the family's own authenticated caller, so every
    authorization rule an application already has applies unchanged.

    The resource owner is loaded through the firewall's own user provider,
    which is why one of these is built per firewall: the same token names a
    different person on an API reading its staff from one store and its
    customers from another. A token issued to a client *for itself* names no
    person, so there is nobody to load and a stand-in carries the client's
    identifier instead.

    It is also the firewall's entry point. A request with no token at all gets
    a ``401`` and a bearer challenge, as one whose token was refused does —
    but a bare one, naming only the realm. RFC 6750 section 3.1 asks that a
    request lacking any authentication information be told no reason: a caller
    that presented nothing has learned nothing about this server beyond that a
    token is how it would be read.
    """

    __slots__ = (
        "_realm",
        "_resource_server",
        "_responses",
        "_role_prefix",
        "_user_provider",
    )

    def __init__(
        self,
        responses: ResponseFactoryInterface,
        resource_server: ResourceServer,
        user_provider: UserProviderInterface,
        role_prefix: str,
        realm: str,
    ) -> None:
        """Read tokens through ``resource_server``, loading users from ``user_provider``.

        Args:
            responses: Builds the refusal responses the entry point answers
                with, so the authenticator names no response class.
            resource_server: What reads the access token and says what it
                carries.
            user_provider: The firewall's own provider, where a resource owner
                is loaded from.
            role_prefix: What each of the token's scopes becomes a role under.
            realm: The protection space the challenge names — the firewall
                this authenticator was built for, since an application serving
                two of them protects two different things.
        """
        self._responses = responses
        self._resource_server = resource_server
        self._user_provider = user_provider
        self._role_prefix = role_prefix
        self._realm = realm

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        """Handle the request only when it carries a bearer token.

        The scheme is read whatever case it was written in: RFC 6750 section
        2.1 writes it ``Bearer``, and it sits on the HTTP authentication
        framework, whose scheme names are case-insensitive (RFC 9110 section
        11.1). A caller writing ``bearer`` is presenting a bearer token.
        """
        header = request.get_header_line("Authorization")

        return header[: len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX

    @override
    async def authenticate(self, request: ServerRequestInterface) -> SelfValidatingPassport:
        """Read the token and build a passport for whoever it names.

        The passport is self-validating: the signature already proved the
        caller, so there is no credential left to check — only the user to
        load.

        Raises:
            OAuth2AuthenticationFailedError: When the resource server will not
                accept the token, or when the token names neither a resource
                owner nor a client, so there is nobody it could be for.
        """
        try:
            read = await self._resource_server.validate_authenticated_request(request)
        except OAuthServerError as error:
            raise OAuth2AuthenticationFailedError.create(
                "The resource server rejected the request.",
                error,
            ) from error
        access_token_id = _text(read.get_attribute(_ACCESS_TOKEN_ID_ATTRIBUTE))
        client_id = _text(read.get_attribute(_CLIENT_ID_ATTRIBUTE))
        user_identifier = _text(read.get_attribute(_USER_ID_ATTRIBUTE))
        scopes = _scopes(read.get_attribute(_SCOPES_ATTRIBUTE))
        # A token issued to a client for itself names no resource owner, and
        # then the client is who is calling.
        identifier = user_identifier or client_id
        if not identifier:
            raise OAuth2AuthenticationFailedError.create(
                "The access token names neither a resource owner nor a client, so there is "
                "nobody it could have been issued to.",
            )

        async def load(wanted: str) -> UserInterface:
            if wanted == client_id:
                return ClientCredentialsUser(client_id)

            return await self._user_provider.load_user_by_identifier(wanted)

        passport = SelfValidatingPassport(UserBadge(identifier, load))
        passport.set_attribute(_PASSPORT_ACCESS_TOKEN_ID, access_token_id)
        passport.set_attribute(_PASSPORT_CLIENT_ID, client_id)
        passport.set_attribute(_PASSPORT_SCOPES, scopes)

        return passport

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Settle on the caller the token proved, its scopes read as roles."""
        return OAuth2Token(
            passport.get_user_badge().get_loaded_user(),
            firewall_name,
            _text(passport.get_attribute(_PASSPORT_ACCESS_TOKEN_ID)),
            _text(passport.get_attribute(_PASSPORT_CLIENT_ID)),
            _scopes(passport.get_attribute(_PASSPORT_SCOPES)),
            self._role_prefix,
        )

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        """Answer a refused token with the status and challenge the refusal carries.

        Anything that is not one of this package's refusals is left alone, for
        whatever raised it to be answered by the firewall.
        """
        del request
        if isinstance(error, OAuth2AuthenticationError):
            return await _refusal(
                self._responses,
                error.get_message_key(),
                error.get_status_code(),
                error.get_headers(),
            )

        return None

    @override
    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        """Answer a request that proved nothing with a ``401`` and a bearer challenge.

        The challenge names the realm and nothing else. RFC 6750 section 3 has
        the scheme followed by one or more auth-param values, so a bare
        ``Bearer`` is no challenge at all; and section 3.1 asks that a request
        lacking any authentication information be told no error code, which is
        what this answers — a refused token is answered by
        :meth:`on_authentication_failure` instead, out of what the refusal
        itself carries.
        """
        del request
        message = (
            error.get_message_key()
            if error is not None
            else "An access token is required to call this."
        )

        return await _refusal(
            self._responses,
            message,
            HTTPStatus.UNAUTHORIZED,
            {"WWW-Authenticate": bearer_challenge("realm", self._realm)},
        )

    @override
    def __repr__(self) -> str:
        """Name the type, the role prefix and the realm, which are configuration."""
        return f"{type(self).__name__}(role_prefix={self._role_prefix!r}, realm={self._realm!r})"


async def _refusal(
    responses: ResponseFactoryInterface,
    message: str,
    status: int,
    headers: Mapping[str, str],
) -> ResponseInterface:
    """Return the answer a caller that did not prove itself gets.

    Forbids every cache from keeping it: a proxy answering another caller's
    request with one principal's refusal would be telling the wrong person
    something about the right one.
    """
    response = responses.create_response(status)
    for name, value in {**headers, "Cache-Control": "no-store", "Pragma": "no-cache"}.items():
        response = response.with_header(name.lower(), value)
    response = response.with_header("content-type", "application/json")
    _ = await response.get_body().write(
        json.dumps({"code": status, "message": message}, separators=(",", ":")).encode(),
    )
    return response


def _text(value: object) -> str:
    """Return ``value`` when it is a string, and the empty string otherwise."""
    return value if isinstance(value, str) else ""


def _scopes(value: object) -> Sequence[str]:
    """Return ``value`` as a tuple of scope names, dropping anything that is not one."""
    if isinstance(value, str):
        return tuple(name for name in value.split(" ") if name != "")
    if isinstance(value, (list, tuple)):
        # What a list read out of an attribute bag holds cannot be known from
        # its type, so every element is checked rather than trusted.
        names = cast("Sequence[object]", value)

        return tuple(name for name in names if isinstance(name, str) and name != "")

    return ()
