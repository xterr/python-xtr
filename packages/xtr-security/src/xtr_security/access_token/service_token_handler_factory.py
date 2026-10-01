"""The factory that points an access-token authenticator at a handler service."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_security.bundle.token_handler_configs import ServiceTokenHandlerConfig

from .token_handler_factory_interface import TokenHandlerFactoryInterface

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["ServiceTokenHandlerFactory"]


@final
class ServiceTokenHandlerFactory(TokenHandlerFactoryInterface):
    """Uses an access-token handler the application registered as a service."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of handler ``id``."""
        return "id"

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`ServiceTokenHandlerConfig`."""
        return ServiceTokenHandlerConfig

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        service_id: str,
        config: object,
    ) -> ServiceKey:
        """Return the key of the handler service the application registered."""
        del services, builder, service_id
        settings = cast("ServiceTokenHandlerConfig", config)
        return (settings.service, settings.qualifier)
