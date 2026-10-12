"""Building the managers that keep clients and credentials in a database.

A factory rather than a plain registration for every one of them, because each
has to read and write through *the connection this deployment named*, and that
name is configuration rather than a service.

Each manager is a singleton, as every other service of this package is, and is
handed the connection registry rather than a session: a session belongs to one
request and a manager is asked by all of them. The registry answers with the
session of the unit of work under way, which is the one the application's own
work in that request is done in — so a token is written in the same
transaction, and committed before the response is produced.
"""

from __future__ import annotations

from collections.abc import (
    Callable,  # noqa: TC003 -- the container evaluates these annotations at runtime
)
from typing import TYPE_CHECKING

# Every name below annotates a factory parameter, and the container evaluates
# those annotations at runtime to decide what to inject, so none can hide under
# TYPE_CHECKING.
from xtr_clock import (
    ClockInterface,  # noqa: TC002 -- the container evaluates these annotations at runtime
)
from xtr_dependency_injection import named_factory
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- the container evaluates these annotations at runtime
    EventDispatcherInterface,
)
from xtr_orm import (
    ConnectionRegistry,  # noqa: TC002 -- the container evaluates these annotations at runtime
)

from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 -- the container evaluates these annotations at runtime
    ClientManagerInterface,
)
from xtr_security_oauth2_server.manager.orm.access_token_manager import AccessTokenManager
from xtr_security_oauth2_server.manager.orm.authorization_code_manager import (
    AuthorizationCodeManager,
)
from xtr_security_oauth2_server.manager.orm.client_manager import ClientManager
from xtr_security_oauth2_server.manager.orm.device_code_manager import DeviceCodeManager
from xtr_security_oauth2_server.manager.orm.refresh_token_manager import RefreshTokenManager
from xtr_security_oauth2_server.service.credentials_revoker.orm_credentials_revoker import (
    OrmCredentialsRevoker,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server.model.abstract_client import AbstractClient

__all__ = [
    "access_token_manager_factory",
    "authorization_code_manager_factory",
    "client_manager_factory",
    "credentials_revoker_factory",
    "device_code_manager_factory",
    "refresh_token_manager_factory",
]


def access_token_manager_factory(
    connection: str,
    persist_access_token: bool,
) -> Callable[..., AccessTokenManager]:
    """Return a factory building the access-token manager on ``connection``."""

    def oauth2_server_orm_access_token_manager(
        connections: ConnectionRegistry,
        clock: ClockInterface,
    ) -> AccessTokenManager:
        return AccessTokenManager(connections, connection, clock, persist_access_token)

    return named_factory(
        oauth2_server_orm_access_token_manager,
        "oauth2_server_orm_access_token_manager",
    )


def authorization_code_manager_factory(
    connection: str,
) -> Callable[..., AuthorizationCodeManager]:
    """Return a factory building the authorization-code manager on ``connection``."""

    def oauth2_server_orm_authorization_code_manager(
        connections: ConnectionRegistry,
        clock: ClockInterface,
    ) -> AuthorizationCodeManager:
        return AuthorizationCodeManager(connections, connection, clock)

    return named_factory(
        oauth2_server_orm_authorization_code_manager,
        "oauth2_server_orm_authorization_code_manager",
    )


def device_code_manager_factory(connection: str) -> Callable[..., DeviceCodeManager]:
    """Return a factory building the device-code manager on ``connection``."""

    def oauth2_server_orm_device_code_manager(
        connections: ConnectionRegistry,
        clock: ClockInterface,
    ) -> DeviceCodeManager:
        return DeviceCodeManager(connections, connection, clock)

    return named_factory(
        oauth2_server_orm_device_code_manager,
        "oauth2_server_orm_device_code_manager",
    )


def refresh_token_manager_factory(connection: str) -> Callable[..., RefreshTokenManager]:
    """Return a factory building the refresh-token manager on ``connection``."""

    def oauth2_server_orm_refresh_token_manager(
        connections: ConnectionRegistry,
        clock: ClockInterface,
    ) -> RefreshTokenManager:
        return RefreshTokenManager(connections, connection, clock)

    return named_factory(
        oauth2_server_orm_refresh_token_manager,
        "oauth2_server_orm_refresh_token_manager",
    )


def client_manager_factory(
    connection: str,
    client_class: type[AbstractClient],
) -> Callable[..., ClientManager]:
    """Return a factory building the client manager for ``client_class``."""

    def oauth2_server_orm_client_manager(
        connections: ConnectionRegistry,
        dispatcher: EventDispatcherInterface,
    ) -> ClientManager:
        return ClientManager(connections, connection, dispatcher, client_class)

    return named_factory(
        oauth2_server_orm_client_manager,
        "oauth2_server_orm_client_manager",
    )


def credentials_revoker_factory(
    connection: str,
    persist_access_token: bool,
    enable_device_code_grant: bool,
) -> Callable[..., OrmCredentialsRevoker]:
    """Return a factory building what withdraws everything issued to one client."""

    def oauth2_server_orm_credentials_revoker(
        connections: ConnectionRegistry,
        client_manager: ClientManagerInterface,
    ) -> OrmCredentialsRevoker:
        return OrmCredentialsRevoker(
            connections,
            connection,
            client_manager,
            persist_access_token,
            enable_device_code_grant,
        )

    return named_factory(
        oauth2_server_orm_credentials_revoker,
        "oauth2_server_orm_credentials_revoker",
    )
