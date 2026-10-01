"""What a bundle implements to add a kind of authenticator to a firewall.

An authenticator factory reads one authenticator configuration and registers the
authenticator services it describes on the container, returning their keys for
the firewall to run. A third-party package adds its own kind of authenticator by
registering a factory through the prepend helpers (seam S-1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["AuthenticatorFactoryInterface"]


@runtime_checkable
class AuthenticatorFactoryInterface(Protocol):
    """Turns one authenticator configuration into authenticator services.

    The bundle sorts a firewall's factories by ``priority`` (highest first),
    matches each configured authenticator to the factory whose ``config_type``
    it is an instance of, and calls :meth:`create_authenticator` to register the
    services and collect their keys.
    """

    @property
    def key(self) -> str:
        """The name of the kind of authenticator, unique among factories."""
        ...

    @property
    def priority(self) -> int:
        """Where this factory's authenticators sit in a firewall's order; higher first."""
        ...

    @property
    def config_type(self) -> type:
        """The configuration class instances of which this factory builds."""
        ...

    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        """Register the authenticator services and return their keys.

        Args:
            services: Where the authenticator services are registered.
            builder: The container builder, for reading other definitions.
            firewall_name: The firewall the authenticators belong to.
            config: The authenticator configuration, an instance of
                :attr:`config_type`.
            user_provider: The key of the firewall's user provider, or ``None``
                when the firewall names none.

        Returns:
            The keys of the authenticator services, in the order they run.
        """
        ...
