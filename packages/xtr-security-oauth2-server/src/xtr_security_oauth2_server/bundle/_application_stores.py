"""The six stores an application answers for itself, named under ``persistence.custom``.

The bundle registers no store of its own then: it points each manager
interface at the service the application named. Which setting named which
interface is written once, here, because two readers need it — the aliasing,
and the refusal that names every store nothing registered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
    RefreshTokenManagerInterface,
)
from xtr_security_oauth2_server.service.credentials_revoker_interface import (
    CredentialsRevokerInterface,
)

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator

    from .persistence_configs import CustomPersistenceConfig

__all__ = ["named_stores", "register_custom"]


def register_custom(
    persistence: CustomPersistenceConfig,
    services: ServiceConfigurator,
) -> None:
    """Point every manager interface at the service the application named."""
    for _setting, interface, store in named_stores(persistence):
        services.alias(interface, store)


def named_stores(
    persistence: CustomPersistenceConfig,
) -> tuple[tuple[str, type, type], ...]:
    """Return every store an application named: its setting, its interface, its class."""
    return (
        (
            "persistence.custom.access_token_manager",
            AccessTokenManagerInterface,
            persistence.access_token_manager,
        ),
        (
            "persistence.custom.authorization_code_manager",
            AuthorizationCodeManagerInterface,
            persistence.authorization_code_manager,
        ),
        (
            "persistence.custom.client_manager",
            ClientManagerInterface,
            persistence.client_manager,
        ),
        (
            "persistence.custom.refresh_token_manager",
            RefreshTokenManagerInterface,
            persistence.refresh_token_manager,
        ),
        (
            "persistence.custom.device_code_manager",
            DeviceCodeManagerInterface,
            persistence.device_code_manager,
        ),
        (
            "persistence.custom.credentials_revoker",
            CredentialsRevokerInterface,
            persistence.credentials_revoker,
        ),
    )
