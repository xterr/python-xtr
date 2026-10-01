"""The factory that chains several named user providers into one."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

# ``ServiceLocator`` and the provider interface annotate a factory parameter the
# container reads at runtime, so both must be importable when it does.
from xtr_dependency_injection import ServiceLocator, named_factory
from xtr_security_core import ChainUserProvider
from xtr_security_core.user.user_provider_interface import (  # noqa: TC002 -- read at runtime
    UserProviderInterface,
)

from xtr_security.bundle.user_provider_configs import ChainUserProviderConfig

from .user_provider_factory_interface import UserProviderFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["ChainUserProviderFactory"]


@final
class ChainUserProviderFactory(UserProviderFactoryInterface):
    """Builds a :class:`~xtr_security_core.ChainUserProvider` from provider names.

    The chain takes a lazy locator over every provider registered under
    :class:`~xtr_security_core.user.user_provider_interface.UserProviderInterface`
    — the same names the security configuration declares them under — and asks it
    for the ones it names, in order. Because the locator builds nothing until
    asked, the chain's own name being one of those keys carries no build cycle,
    so a chain may name another chain.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of provider ``chain``."""
        return "chain"

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`ChainUserProviderConfig`."""
        return ChainUserProviderConfig

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        provider_name: str,
        config: object,
    ) -> ServiceKey:
        """Register the factory chaining the providers the configuration names."""
        del builder
        settings = cast("ChainUserProviderConfig", config)
        return services.set(
            _chain_factory(provider_name, settings.providers), qualifier=provider_name
        ).key


def _chain_factory(
    provider_name: str,
    members: tuple[str, ...],
) -> Callable[..., Awaitable[ChainUserProvider]]:
    """Return a factory resolving ``members`` from the locator, in the order named."""

    async def chain_user_provider(
        providers: ServiceLocator[UserProviderInterface],
    ) -> ChainUserProvider:
        return ChainUserProvider([await providers.get(member) for member in members])

    return named_factory(chain_user_provider, f"user_provider_{provider_name}")
