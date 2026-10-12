"""Building each shipped grant, configured as the deployment asked for it.

A factory rather than a plain registration for every grant that has anything
set on it after it is built: the container holds no method calls, so what
upstream does with ``addMethodCall`` happens here instead — the refresh-token
lifetime, the proof-key requirement, what a device is told about polling.

Each factory returns its own grant class, so the definition is still keyed by
that class: autoconfiguration recognises it as a grant and the grant pass
aliases it by type, exactly as it would a plainly registered one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Every name below annotates a factory parameter, and the container evaluates
# those annotations to decide what to inject, so none can hide under
# TYPE_CHECKING.
from xtr_clock import (
    ClockInterface,  # noqa: TC002 -- the container evaluates these factory annotations at runtime
)
from xtr_dependency_injection import named_factory
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- the container evaluates these factory annotations at runtime
    EventDispatcherInterface,
)

from xtr_security_oauth2_server.grant.auth_code_grant import AuthCodeGrant
from xtr_security_oauth2_server.grant.client_credentials_grant import ClientCredentialsGrant
from xtr_security_oauth2_server.grant.device_code_grant import DeviceCodeGrant
from xtr_security_oauth2_server.grant.implicit_grant import ImplicitGrant
from xtr_security_oauth2_server.grant.password_grant import PasswordGrant
from xtr_security_oauth2_server.grant.refresh_token_grant import RefreshTokenGrant
from xtr_security_oauth2_server.repositories.auth_code_repository_interface import (  # noqa: TC001 -- the container evaluates these factory annotations at runtime
    AuthCodeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.device_code_repository_interface import (  # noqa: TC001 -- the container evaluates these factory annotations at runtime
    DeviceCodeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (  # noqa: TC001 -- the container evaluates these factory annotations at runtime
    RefreshTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.user_repository_interface import (  # noqa: TC001 -- the container evaluates these factory annotations at runtime
    UserRepositoryInterface,
)

from ._required_settings import supplied

if TYPE_CHECKING:
    from collections.abc import Callable

    from .authorization_server_config import AuthorizationServerConfig

__all__ = [
    "auth_code_grant_factory",
    "client_credentials_grant_factory",
    "device_code_grant_factory",
    "implicit_grant_factory",
    "password_grant_factory",
    "refresh_token_grant_factory",
]


def client_credentials_grant_factory() -> Callable[..., ClientCredentialsGrant]:
    """Return a factory building the grant a client uses to act for itself."""

    def oauth2_server_client_credentials_grant(
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
    ) -> ClientCredentialsGrant:
        return ClientCredentialsGrant(dispatcher, clock)

    return named_factory(
        oauth2_server_client_credentials_grant,
        "oauth2_server_client_credentials_grant",
    )


def auth_code_grant_factory(
    config: AuthorizationServerConfig,
) -> Callable[..., AuthCodeGrant]:
    """Return a factory building the browser redirect flow."""
    auth_code_ttl = config.auth_code_ttl
    refresh_token_ttl = config.refresh_token_ttl
    require_code_challenge = config.require_code_challenge_for_public_clients

    def oauth2_server_auth_code_grant(
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        auth_code_repository: AuthCodeRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> AuthCodeGrant:
        grant = AuthCodeGrant(
            dispatcher,
            clock,
            auth_code_repository,
            refresh_token_repository,
            auth_code_ttl,
        )
        grant.set_refresh_token_ttl(refresh_token_ttl)
        if not require_code_challenge:
            # A deployment that turns this off is saying its public clients
            # cannot do a proof key; every one of them is then open to an
            # intercepted code being redeemed by whoever intercepted it.
            grant.disable_require_code_challenge_for_public_clients()

        return grant

    return named_factory(oauth2_server_auth_code_grant, "oauth2_server_auth_code_grant")


def refresh_token_grant_factory(
    config: AuthorizationServerConfig,
) -> Callable[..., RefreshTokenGrant]:
    """Return a factory building the grant that spends a refresh token."""
    refresh_token_ttl = config.refresh_token_ttl

    def oauth2_server_refresh_token_grant(
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> RefreshTokenGrant:
        grant = RefreshTokenGrant(dispatcher, clock, refresh_token_repository)
        grant.set_refresh_token_ttl(refresh_token_ttl)

        return grant

    return named_factory(
        oauth2_server_refresh_token_grant,
        "oauth2_server_refresh_token_grant",
    )


def password_grant_factory(
    config: AuthorizationServerConfig,
) -> Callable[..., PasswordGrant]:
    """Return a factory building the grant that takes a resource owner's password."""
    refresh_token_ttl = config.refresh_token_ttl

    def oauth2_server_password_grant(
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        user_repository: UserRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> PasswordGrant:
        grant = PasswordGrant(
            dispatcher,
            clock,
            user_repository,
            refresh_token_repository,
        )
        grant.set_refresh_token_ttl(refresh_token_ttl)

        return grant

    return named_factory(oauth2_server_password_grant, "oauth2_server_password_grant")


def implicit_grant_factory(
    config: AuthorizationServerConfig,
) -> Callable[..., ImplicitGrant]:
    """Return a factory building the grant that hands a token to the browser."""
    access_token_ttl = config.access_token_ttl

    def oauth2_server_implicit_grant(
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
    ) -> ImplicitGrant:
        return ImplicitGrant(dispatcher, clock, access_token_ttl)

    return named_factory(oauth2_server_implicit_grant, "oauth2_server_implicit_grant")


def device_code_grant_factory(
    config: AuthorizationServerConfig,
) -> Callable[..., DeviceCodeGrant]:
    """Return a factory building the flow for something with no browser."""
    device_code_ttl = config.device_code_ttl
    verification_uri = config.device_code_verification_uri
    retry_interval = config.device_code_polling_interval
    refresh_token_ttl = config.refresh_token_ttl
    include_complete = config.enable_device_code_verification_uri_complete_generation
    interval_visible = config.enable_device_code_polling_interval_visibility

    def oauth2_server_device_code_grant(
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        device_code_repository: DeviceCodeRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> DeviceCodeGrant:
        grant = DeviceCodeGrant(
            dispatcher,
            clock,
            device_code_repository,
            refresh_token_repository,
            device_code_ttl,
            supplied(
                verification_uri,
                "authorization_server.device_code_verification_uri",
                "a device could not be told where its owner should go to type the user code",
            ),
            retry_interval,
        )
        grant.set_refresh_token_ttl(refresh_token_ttl)
        grant.set_include_verification_uri_complete(include_complete)
        grant.set_interval_visibility(interval_visible)

        return grant

    return named_factory(oauth2_server_device_code_grant, "oauth2_server_device_code_grant")
