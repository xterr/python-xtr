"""What stands in for the stores when a deployment has named no persistence.

The bundle has to build without configuration, and a server with nowhere to
keep its clients and credentials cannot work — so every store is registered as
something that refuses, naming the setting, the first time one is asked for.
Registering nothing instead would leave the container reporting an unknown
service and a missing alias, which says nothing about the setting that is
missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_dependency_injection import named_factory

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

from ._required_settings import refuse_without_persistence

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["UNCONFIGURED_STORES", "unconfigured_store_factories"]

UNCONFIGURED_STORES: tuple[type, ...] = (
    AccessTokenManagerInterface,
    AuthorizationCodeManagerInterface,
    ClientManagerInterface,
    DeviceCodeManagerInterface,
    RefreshTokenManagerInterface,
    CredentialsRevokerInterface,
)
"""Every store a persistence supplies, each of which has to answer for itself."""


def unconfigured_store_factories() -> tuple[Callable[..., object], ...]:
    """Return one refusing factory per store, each keyed by the interface it fills."""
    return tuple(_refusing(interface) for interface in UNCONFIGURED_STORES)


def _refusing(interface: type) -> Callable[..., object]:
    """Return a factory of ``interface`` that refuses, naming the missing setting."""

    def oauth2_server_unconfigured_store() -> object:
        refuse_without_persistence()

    oauth2_server_unconfigured_store.__annotations__ = {"return": interface}

    return named_factory(
        oauth2_server_unconfigured_store,
        f"oauth2_server_unconfigured_{interface.__name__}",
    )
