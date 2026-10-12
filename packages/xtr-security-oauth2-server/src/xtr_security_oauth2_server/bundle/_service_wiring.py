"""Registering what the protocol engine is made of: keys, bridges, scopes, grants, servers.

Everything between the stores underneath and the endpoints on top. Kept apart
from the bundle so that each half stays a module a reader can hold in their
head, and in one piece because the order matters: the keys are registered
before what signs with them, and the grants before the server that replays
them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.converter.scope_converter_interface import (
    ScopeConverterInterface,
)
from xtr_security_oauth2_server.converter.user_converter import UserConverter
from xtr_security_oauth2_server.converter.user_converter_interface import UserConverterInterface
from xtr_security_oauth2_server.event.authorization_request_resolve_event_factory import (
    AuthorizationRequestResolveEventFactory,
)
from xtr_security_oauth2_server.manager.in_memory.scope_manager import ScopeManager
from xtr_security_oauth2_server.manager.scope_manager_interface import ScopeManagerInterface
from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.auth_code_repository_interface import (
    AuthCodeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.device_code_repository_interface import (
    DeviceCodeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.scope_repository_interface import (
    ScopeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from xtr_security_oauth2_server.repository.access_token_repository import AccessTokenRepository
from xtr_security_oauth2_server.repository.auth_code_repository import AuthCodeRepository
from xtr_security_oauth2_server.repository.client_repository import ClientRepository
from xtr_security_oauth2_server.repository.device_code_repository import DeviceCodeRepository
from xtr_security_oauth2_server.repository.null_access_token_repository import (
    NullAccessTokenRepository,
)
from xtr_security_oauth2_server.repository.refresh_token_repository import RefreshTokenRepository
from xtr_security_oauth2_server.repository.scope_repository import ScopeRepository
from xtr_security_oauth2_server.repository.user_repository import UserRepository
from xtr_security_oauth2_server.resource_server import ResourceServer
from xtr_security_oauth2_server.response_types.bearer_token_response import BearerTokenResponse
from xtr_security_oauth2_server.response_types.response_type_interface import (
    ResponseTypeInterface,
)

from ._grant_factories import (
    auth_code_grant_factory,
    client_credentials_grant_factory,
    device_code_grant_factory,
    implicit_grant_factory,
    password_grant_factory,
    refresh_token_grant_factory,
)
from ._server_factories import authorization_server_factory, token_server_factory
from ._service_factories import (
    bearer_token_validator_factory,
    client_repository_factory,
    password_hasher_factory,
    scope_manager_factory,
)
from ._signing_factories import QUALIFIER, jws_provider_factory, key_loader_factory, signer_factory
from .grant_type_pass import GRANT_TAG

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator

    from .oauth2_server_config import OAuth2ServerConfig

__all__ = [
    "register_access_token_saving",
    "register_grants",
    "register_repositories",
    "register_response_type",
    "register_scopes",
    "register_servers",
    "register_signing",
]


def register_signing(config: OAuth2ServerConfig, services: ServiceConfigurator) -> None:
    """Register this package's own keys, under a qualifier of its own.

    Never under the bare interfaces: the self-issued-token package owns those,
    and the documented deployment runs both bundles — one firewall signs in the
    end user, this server signs access tokens — so each has to keep its own
    key.
    """
    from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import (  # noqa: PLC0415 -- imported beside the interface it is aliased under
        JoserfcJwsProvider,
    )
    from xtr_security_jwt.services.jws_provider.jws_provider_interface import (  # noqa: PLC0415 -- imported beside the implementation it aliases
        JwsProviderInterface,
    )
    from xtr_security_jwt.services.key_loader import (  # noqa: PLC0415 -- imported beside the interface it is aliased under
        RawKeyLoader,
    )
    from xtr_security_jwt.services.key_loader.key_loader_interface import (  # noqa: PLC0415 -- imported beside the implementation it aliases
        KeyLoaderInterface,
    )

    server = config.authorization_server
    _ = services.set(key_loader_factory(server, config.resource_server), qualifier=QUALIFIER)
    services.alias(
        KeyLoaderInterface,
        RawKeyLoader,
        alias_qualifier=QUALIFIER,
        target_qualifier=QUALIFIER,
    )
    _ = services.set(jws_provider_factory(server), qualifier=QUALIFIER)
    services.alias(
        JwsProviderInterface,
        JoserfcJwsProvider,
        alias_qualifier=QUALIFIER,
        target_qualifier=QUALIFIER,
    )
    _ = services.set(signer_factory(server))


def register_access_token_saving(
    config: OAuth2ServerConfig,
    services: ServiceConfigurator,
) -> None:
    """Register the access-token store, or the one that keeps no record."""
    if config.authorization_server.persist_access_token:
        _ = services.set(AccessTokenRepository)
        services.alias(AccessTokenRepositoryInterface, AccessTokenRepository)

        return
    _ = services.set(NullAccessTokenRepository)
    services.alias(AccessTokenRepositoryInterface, NullAccessTokenRepository)


def register_repositories(services: ServiceConfigurator) -> None:
    """Register the bridges between the protocol and whatever stores it."""
    _ = services.set(ScopeConverter)
    services.alias(ScopeConverterInterface, ScopeConverter)
    _ = services.set(UserConverter)
    services.alias(UserConverterInterface, UserConverter)
    # Its own hasher, under this package's qualifier: a client secret is not a
    # user password and must not share one configuration with them.
    _ = services.set(password_hasher_factory(), qualifier=QUALIFIER)
    _ = services.set(client_repository_factory())
    services.alias(ClientRepositoryInterface, ClientRepository)
    _ = services.set(AuthCodeRepository)
    services.alias(AuthCodeRepositoryInterface, AuthCodeRepository)
    _ = services.set(RefreshTokenRepository)
    services.alias(RefreshTokenRepositoryInterface, RefreshTokenRepository)
    _ = services.set(DeviceCodeRepository)
    services.alias(DeviceCodeRepositoryInterface, DeviceCodeRepository)
    _ = services.set(ScopeRepository)
    services.alias(ScopeRepositoryInterface, ScopeRepository)
    _ = services.set(UserRepository)
    services.alias(UserRepositoryInterface, UserRepository)
    _ = services.set(AuthorizationRequestResolveEventFactory)


def register_scopes(config: OAuth2ServerConfig, services: ServiceConfigurator) -> None:
    """Register the vocabulary of scopes this deployment knows.

    Always in memory, whatever the persistence: the available scopes are
    configuration rather than data, so there is nothing to store and nothing to
    migrate when they change.
    """
    _ = services.set(scope_manager_factory(config.scopes.available))
    services.alias(ScopeManagerInterface, ScopeManager)


def register_grants(config: OAuth2ServerConfig, services: ServiceConfigurator) -> None:
    """Register each flow this deployment turned on, tagged with its lifetime."""
    server = config.authorization_server
    ttl = server.access_token_ttl
    turned_on = (
        (server.enable_client_credentials_grant, client_credentials_grant_factory()),
        (server.enable_auth_code_grant, auth_code_grant_factory(server)),
        (server.enable_refresh_token_grant, refresh_token_grant_factory(server)),
        (server.enable_device_code_grant, device_code_grant_factory(server)),
        (server.enable_password_grant, password_grant_factory(server)),
        (server.enable_implicit_grant, implicit_grant_factory(server)),
    )
    for enabled, factory in turned_on:
        if enabled:
            _ = services.set(factory).add_tag(GRANT_TAG, access_token_ttl=ttl)


def register_response_type(config: OAuth2ServerConfig, services: ServiceConfigurator) -> None:
    """Register what the token endpoint answers with."""
    configured = config.authorization_server.response_type_class
    if configured is None:
        _ = services.set(BearerTokenResponse)
        services.alias(ResponseTypeInterface, BearerTokenResponse)

        return
    # Registered as a service of its own so that its constructor may take
    # services, which is what an add-on's response type needs.
    _ = services.set(configured)
    services.alias(ResponseTypeInterface, configured)


def register_servers(config: OAuth2ServerConfig, services: ServiceConfigurator) -> None:
    """Register the three servers and the reading of a token they share."""
    from xtr_security_oauth2_server.authorization_validators.authorization_validator_interface import (  # noqa: E501, PLC0415 -- one dotted path, imported beside what it aliases
        AuthorizationValidatorInterface,
    )
    from xtr_security_oauth2_server.authorization_validators.bearer_token_validator import (  # noqa: PLC0415 -- imported beside the interface it is aliased under
        BearerTokenValidator,
    )

    server = config.authorization_server
    _ = services.set(bearer_token_validator_factory(server, config.resource_server))
    services.alias(AuthorizationValidatorInterface, BearerTokenValidator)
    _ = services.set(ResourceServer)
    _ = services.set(token_server_factory(server, config.resource_server))
    _ = services.set(authorization_server_factory(server))
