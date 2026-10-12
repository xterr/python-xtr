"""Building the pieces of a deployment that are not the servers themselves.

A factory rather than a plain registration wherever something cannot be handed
over as a value: this package's own JWS provider and hasher live under a
qualifier, the issuer and the vocabulary of scopes are settings only the
deployment can supply, and both are read where they are used rather than when
the container is built.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from xtr_clock import ClockInterface
from xtr_dependency_injection import Target, named_factory
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_logging_contracts import LoggerInterface
from xtr_password_hasher import PasswordHasherInterface, create_auto_password_hasher
from xtr_security import Security
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.key_loader.key_loader_interface import KeyLoaderInterface

from xtr_security_oauth2_server.authorization_server import AuthorizationServer
from xtr_security_oauth2_server.authorization_validators.bearer_token_validator import (
    BearerTokenValidator,
)
from xtr_security_oauth2_server.controller.authorization_controller import AuthorizationController
from xtr_security_oauth2_server.controller.jwks_controller import JwksController
from xtr_security_oauth2_server.converter.user_converter_interface import UserConverterInterface
from xtr_security_oauth2_server.event.authorization_request_resolve_event_factory import (
    AuthorizationRequestResolveEventFactory,
)
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.manager.in_memory.scope_manager import ScopeManager
from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repository.client_repository import ClientRepository

from ._required_settings import supplied, supplied_scopes
from ._signing_factories import QUALIFIER

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from .authorization_server_config import AuthorizationServerConfig
    from .resource_server_config import ResourceServerConfig

__all__ = [
    "authorization_controller_factory",
    "bearer_token_validator_factory",
    "client_repository_factory",
    "jwks_controller_factory",
    "password_hasher_factory",
    "scope_manager_factory",
]

#: What cannot be done when this server does not know who it is.
_NAMELESS = "a token could not be checked against the server that issued it"


def password_hasher_factory() -> Callable[..., PasswordHasherInterface]:
    """Return a factory building what a client's secret is hashed with.

    Its own hasher, under this package's qualifier, rather than whatever an
    application hashes *user* passwords with: a client secret is machine-made
    and rotated by an administrator, so the two have no reason to share a
    configuration — and an application changing how it stores its users'
    passwords must not silently invalidate every registered client's secret.

    The secure default of the hashing package: argon2id, with the older schemes
    still verifying behind it, so a secret hashed by an earlier deployment keeps
    working and is re-hashed the next time it is proved.
    """

    def oauth2_server_password_hasher() -> PasswordHasherInterface:
        return create_auto_password_hasher()

    return named_factory(oauth2_server_password_hasher, "oauth2_server_password_hasher")


def client_repository_factory() -> Callable[..., ClientRepository]:
    """Return a factory building the client repository over the qualified hasher."""

    def oauth2_server_client_repository(
        client_manager: ClientManagerInterface,
        password_hasher: PasswordHasherInterface,
    ) -> ClientRepository:
        return ClientRepository(client_manager, password_hasher)

    oauth2_server_client_repository.__annotations__ = {
        "client_manager": ClientManagerInterface,
        "password_hasher": Annotated[PasswordHasherInterface, Target(QUALIFIER)],
        "return": ClientRepository,
    }

    return named_factory(
        oauth2_server_client_repository,
        "oauth2_server_client_repository",
    )


def bearer_token_validator_factory(
    authorization_server: AuthorizationServerConfig,
    resource_server: ResourceServerConfig,
) -> Callable[..., BearerTokenValidator]:
    """Return a factory building what reads an access token presented to an API."""
    issuer = authorization_server.issuer
    audience = authorization_server.audience
    leeway = resource_server.jwt_leeway

    def oauth2_server_bearer_token_validator(
        access_token_repository: AccessTokenRepositoryInterface,
        jws_provider: JoserfcJwsProvider,
        clock: ClockInterface,
    ) -> BearerTokenValidator:
        return BearerTokenValidator(
            access_token_repository,
            jws_provider,
            supplied(issuer, "authorization_server.issuer", _NAMELESS),
            clock,
            audience,
            leeway,
        )

    oauth2_server_bearer_token_validator.__annotations__ = {
        "access_token_repository": AccessTokenRepositoryInterface,
        "jws_provider": Annotated[JoserfcJwsProvider, Target(QUALIFIER)],
        "clock": ClockInterface,
        "return": BearerTokenValidator,
    }

    return named_factory(
        oauth2_server_bearer_token_validator,
        "oauth2_server_bearer_token_validator",
    )


def jwks_controller_factory(
    config: AuthorizationServerConfig,
) -> Callable[..., JwksController]:
    """Return a factory building the endpoint that publishes the verifying keys."""
    algorithm = config.signature_algorithm

    def oauth2_server_jwks_controller(key_loader: KeyLoaderInterface) -> JwksController:
        return JwksController(key_loader, algorithm)

    oauth2_server_jwks_controller.__annotations__ = {
        "key_loader": Annotated[KeyLoaderInterface, Target(QUALIFIER)],
        "return": JwksController,
    }

    return named_factory(oauth2_server_jwks_controller, "oauth2_server_jwks_controller")


def scope_manager_factory(available: Sequence[str]) -> Callable[..., ScopeManager]:
    """Return a factory building the vocabulary of scopes this deployment knows.

    A factory rather than a definition argument so that a deployment that named
    no scope is told which setting is missing when the vocabulary is first
    asked for, instead of quietly knowing none.
    """

    def oauth2_server_scope_manager() -> ScopeManager:
        return ScopeManager(supplied_scopes(available))

    return named_factory(oauth2_server_scope_manager, "oauth2_server_scope_manager")


def authorization_controller_factory(
    log_channel: str | None,
) -> Callable[..., AuthorizationController]:
    """Return a factory building the endpoint a resource owner's browser arrives at.

    A factory rather than a plain registration because of the one dependency
    that may not be there: the endpoint reports a request that arrived with
    nobody authenticated, and logging is a peer a deployment need not run.
    The parameter is declared only when ``log_channel`` names a channel whose
    logger the container holds, so nothing is handed the container to probe
    for one — and a deployment that logs nothing builds the same endpoint
    without it.
    """

    def oauth2_server_authorization_controller(  # noqa: PLR0913, PLR0917 -- one endpoint's worth of wiring
        server: AuthorizationServer,
        dispatcher: EventDispatcherInterface,
        event_factory: AuthorizationRequestResolveEventFactory,
        user_converter: UserConverterInterface,
        client_manager: ClientManagerInterface,
        security: Security,
        logger: LoggerInterface | None = None,
    ) -> AuthorizationController:
        return AuthorizationController(
            server,
            dispatcher,
            event_factory,
            user_converter,
            client_manager,
            security,
            logger,
        )

    annotations: dict[str, object] = {
        "server": AuthorizationServer,
        "dispatcher": EventDispatcherInterface,
        "event_factory": AuthorizationRequestResolveEventFactory,
        "user_converter": UserConverterInterface,
        "client_manager": ClientManagerInterface,
        "security": Security,
        "return": AuthorizationController,
    }
    if log_channel is not None:
        annotations["logger"] = Annotated[LoggerInterface, Target(log_channel)]
    oauth2_server_authorization_controller.__annotations__ = annotations

    return named_factory(
        oauth2_server_authorization_controller,
        "oauth2_server_authorization_controller",
    )
