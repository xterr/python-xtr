"""The factory that points a firewall at a user provider the container provides."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_security.bundle.user_provider_configs import ServiceUserProviderConfig

from .user_provider_factory_interface import UserProviderFactoryInterface

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["ServiceUserProviderFactory"]


@final
class ServiceUserProviderFactory(UserProviderFactoryInterface):
    """Uses a user provider the application registered as a service, by type and qualifier."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of provider ``service``."""
        return "service"

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`ServiceUserProviderConfig`."""
        return ServiceUserProviderConfig

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        provider_name: str,
        config: object,
    ) -> ServiceKey:
        """Return the key of the service the application already registered."""
        del services, builder, provider_name
        settings = cast("ServiceUserProviderConfig", config)
        return (settings.service, settings.qualifier)
