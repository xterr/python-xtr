"""The factory that builds an in-memory user provider from inline users."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_security_core import InMemoryUserProvider

from xtr_security.bundle.user_provider_configs import InMemoryUserProviderConfig

from .user_provider_factory_interface import UserProviderFactoryInterface

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["InMemoryUserProviderFactory"]


@final
class InMemoryUserProviderFactory(UserProviderFactoryInterface):
    """Builds an :class:`~xtr_security_core.InMemoryUserProvider` from a table of users."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of provider ``in_memory``."""
        return "in_memory"

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`InMemoryUserProviderConfig`."""
        return InMemoryUserProviderConfig

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        provider_name: str,
        config: object,
    ) -> ServiceKey:
        """Register the in-memory provider under ``provider_name`` and return its key."""
        del builder
        settings = cast("InMemoryUserProviderConfig", config)
        provider = InMemoryUserProvider(dict(settings.users))
        return services.instance(provider, qualifier=provider_name).key
