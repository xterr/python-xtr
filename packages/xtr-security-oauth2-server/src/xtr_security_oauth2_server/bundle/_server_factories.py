"""Building the two servers a deployment answers requests through.

A factory rather than a plain registration because neither can be handed over
as a value: the authorization server has to replay the grants a compiler pass
collected, and both read the key their own payloads are sealed with — a setting
only the deployment can supply, so it is read when a server is built rather
than when the container is.
"""

from __future__ import annotations

# These three are read at runtime: each appears inside a factory's explicit
# ``__annotations__``, which the container evaluates to key the service.
from collections.abc import (
    Hashable,
    Mapping,
)
from datetime import (
    timedelta,
)
from typing import TYPE_CHECKING, Annotated, Literal, cast

from xtr_clock import ClockInterface
from xtr_dependency_injection import Target, named_factory
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
from xtr_security_oauth2_server_core.entities.access_token_signer import AccessTokenSigner
from xtr_security_oauth2_server_core.grant.grant_type_interface import GrantTypeInterface
from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.scope_repository_interface import (
    ScopeRepositoryInterface,
)
from xtr_security_oauth2_server_core.response_types.response_type_interface import (
    ResponseTypeInterface,
)
from xtr_security_oauth2_server_core.token_server import TokenServer

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

from ._required_settings import supplied
from ._signing_factories import QUALIFIER

if TYPE_CHECKING:
    from collections.abc import Callable

    from .authorization_server_config import AuthorizationServerConfig
    from .resource_server_config import ResourceServerConfig

__all__ = [
    "authorization_server_factory",
    "token_server_factory",
]

#: What cannot be done when no key seals this server's own payloads.
_UNSEALED = (
    "an authorization code and a refresh token are this server's own payloads handed to a "
    "client, and there is no key to seal them with"
)

#: How a deployment comes by one. Not the key-pair command: that writes the
#: PEM pair this server *signs* with, which is a different key entirely.
_MINT_ENCRYPTION_KEY = (
    "Mint one for encryption_key_type='key' with: python -c \"import base64, secrets; "
    "print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='))\". "
    "The 'plain' type takes a password of at least 32 characters instead."
)

#: What cannot be done when this server does not know who it is.
_NAMELESS = "a token could not be checked against the server that issued it"


def token_server_factory(
    authorization_server: AuthorizationServerConfig,
    resource_server: ResourceServerConfig,
) -> Callable[..., TokenServer]:
    """Return a factory building the server the revoke and introspect endpoints use."""
    issuer = authorization_server.issuer
    audience = authorization_server.audience
    leeway = resource_server.jwt_leeway

    def oauth2_server_token_server(  # noqa: PLR0913, PLR0917 -- one server's worth of wiring
        client_repository: ClientRepositoryInterface,
        access_token_repository: AccessTokenRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
        jws_provider: JoserfcJwsProvider,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        encryption_key: str = "",
        encryption_key_type: str = "plain",
    ) -> TokenServer:
        return TokenServer(
            client_repository,
            access_token_repository,
            refresh_token_repository,
            jws_provider,
            supplied(issuer, "authorization_server.issuer", _NAMELESS),
            supplied(
                encryption_key,
                "authorization_server.encryption_key",
                _UNSEALED,
                _MINT_ENCRYPTION_KEY,
            ),
            _key_type(encryption_key_type),
            dispatcher,
            clock,
            audience,
            leeway,
        )

    oauth2_server_token_server.__annotations__ = {
        "client_repository": ClientRepositoryInterface,
        "access_token_repository": AccessTokenRepositoryInterface,
        "refresh_token_repository": RefreshTokenRepositoryInterface,
        "jws_provider": Annotated[JoserfcJwsProvider, Target(QUALIFIER)],
        "dispatcher": EventDispatcherInterface,
        "clock": ClockInterface,
        "encryption_key": str,
        "encryption_key_type": str,
        "return": TokenServer,
    }

    return named_factory(oauth2_server_token_server, "oauth2_server_token_server")


def authorization_server_factory(
    config: AuthorizationServerConfig,
) -> Callable[..., AuthorizationServer]:
    """Return a factory building the server every issuing endpoint goes through.

    The grants are replayed here, in the order a compiler pass collected them,
    because a container holds no method calls: what the pass can record is the
    order and the lifetime each grant issues for, and this is where that
    becomes a configured server.

    No default scope is set on the server. A request naming no scope is
    answered as the protocol says it is — the client's registered scopes, or
    none — and ``scopes.default`` is what a *client* is registered with, which
    is the listener's business rather than the server's.
    """
    revoke_refresh_tokens = config.revoke_refresh_tokens

    def oauth2_server_authorization_server(  # noqa: PLR0913, PLR0917 -- one server's worth of wiring
        client_repository: ClientRepositoryInterface,
        access_token_repository: AccessTokenRepositoryInterface,
        scope_repository: ScopeRepositoryInterface,
        private_key: AccessTokenSigner,
        dispatcher: EventDispatcherInterface,
        response_type: ResponseTypeInterface,
        all_grants: Mapping[Hashable, GrantTypeInterface],
        encryption_key: str = "",
        encryption_key_type: str = "plain",
        grants: tuple[tuple[str, timedelta], ...] = (),
    ) -> AuthorizationServer:
        server = AuthorizationServer(
            client_repository,
            access_token_repository,
            scope_repository,
            private_key,
            supplied(
                encryption_key,
                "authorization_server.encryption_key",
                _UNSEALED,
                _MINT_ENCRYPTION_KEY,
            ),
            _key_type(encryption_key_type),
            dispatcher,
            response_type,
        )
        # It reaches every grant as it is enabled, so it is set first.
        server.revoke_refresh_tokens(revoke_refresh_tokens)
        enabled: dict[str, str] = {}
        for qualifier, access_token_ttl in grants:
            grant = all_grants[qualifier]
            identifier = grant.get_identifier()
            clashed = enabled.get(identifier)
            if clashed is not None:
                raise InvalidConfigurationError(
                    f"Two grants both answer requests for {identifier!r}: {clashed} and "
                    f"{type(grant).__qualname__}. One name means one flow, so enabling both "
                    "would silently leave whichever was registered last. Turn off the shipped "
                    f"grant with its authorization_server enable_* setting, or give yours its "
                    "own identifier.",
                )
            enabled[identifier] = type(grant).__qualname__
            server.enable_grant_type(grant, access_token_ttl)

        return server

    oauth2_server_authorization_server.__annotations__ = {
        "client_repository": ClientRepositoryInterface,
        "access_token_repository": AccessTokenRepositoryInterface,
        "scope_repository": ScopeRepositoryInterface,
        "private_key": AccessTokenSigner,
        "dispatcher": EventDispatcherInterface,
        "response_type": ResponseTypeInterface,
        "all_grants": Mapping[Hashable, GrantTypeInterface],
        "encryption_key": str,
        "encryption_key_type": str,
        "grants": tuple[tuple[str, timedelta], ...],
        "return": AuthorizationServer,
    }

    return named_factory(
        oauth2_server_authorization_server,
        "oauth2_server_authorization_server",
    )


def _key_type(named: str) -> Literal["plain", "key"]:
    """Return ``named`` as one of the two kinds of key there are.

    The compiler pass that reads the parameter has already refused anything
    else, so this only narrows what it validated.
    """
    return cast('Literal["plain", "key"]', named)
