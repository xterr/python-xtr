"""What a bundle implements to add a kind of access-token handler.

A token-handler factory reads one token-handler configuration and registers the
handler service it describes on the container, returning its key. The access-token
authenticator factory looks a handler factory up by its ``key`` to build the
handler a firewall's bearer authenticator validates tokens with (seam S-2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["TokenHandlerFactoryInterface"]


@runtime_checkable
class TokenHandlerFactoryInterface(Protocol):
    """Turns one token-handler configuration into a handler service."""

    @property
    def key(self) -> str:
        """The name of the kind of handler, unique among token-handler factories."""
        ...

    @property
    def config_type(self) -> type:
        """The configuration class instances of which this factory builds."""
        ...

    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        service_id: str,
        config: object,
    ) -> ServiceKey:
        """Register the handler service and return its key.

        Args:
            services: Where the handler service is registered.
            builder: The container builder, for reading other definitions.
            service_id: A name unique to the handler being built, for a
                qualifier when the same handler type serves several firewalls.
            config: The handler configuration, an instance of :attr:`config_type`.

        Returns:
            The key of the handler service.
        """
        ...
