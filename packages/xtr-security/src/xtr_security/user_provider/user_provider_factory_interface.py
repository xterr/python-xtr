"""What a bundle implements to add a kind of user provider.

A user-provider factory reads one user-provider configuration and registers the
provider service it describes on the container, returning its key for a firewall
to load users through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["UserProviderFactoryInterface"]


@runtime_checkable
class UserProviderFactoryInterface(Protocol):
    """Turns one user-provider configuration into a provider service."""

    @property
    def key(self) -> str:
        """The name of the kind of provider, unique among user-provider factories."""
        ...

    @property
    def config_type(self) -> type:
        """The configuration class instances of which this factory builds."""
        ...

    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        provider_name: str,
        config: object,
    ) -> ServiceKey:
        """Register the provider service and return its key.

        Args:
            services: Where the provider service is registered.
            builder: The container builder, for reading other definitions.
            provider_name: The name the provider is registered under, used as a
                qualifier so a firewall resolves it by name.
            config: The provider configuration, an instance of :attr:`config_type`.

        Returns:
            The key of the provider service.
        """
        ...
