"""The factory that builds an in-memory user provider from inline users."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final, override

from xtr_dependency_injection.config.env_placeholder import env_placeholders_in
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
        """Register the in-memory provider under ``provider_name`` and return its key.

        Registered as a factory over the user table, not as a built provider: the table
        may hold ``env(...)`` placeholders — a password hash read from the environment —
        and the container resolves those in what a factory closes over before calling
        it. A provider built here would keep the placeholders as the users' values.

        A table holding none is checked now, so a malformed user fails the build; one
        holding a placeholder is checked when the provider is built, against the values
        the variables hold.

        Raises:
            InvalidArgumentError: If a user's fields cannot build a user — a non-boolean
                ``enabled``, say — and the table holds no placeholder.
        """
        del builder
        settings = cast("InMemoryUserProviderConfig", config)
        users = dict(settings.users)
        if not env_placeholders_in(users):
            _ = InMemoryUserProvider(users)

        def in_memory_user_provider() -> InMemoryUserProvider:
            return InMemoryUserProvider(users)

        in_memory_user_provider.__name__ = f"in_memory_user_provider_{provider_name}"
        in_memory_user_provider.__qualname__ = in_memory_user_provider.__name__
        return services.set(in_memory_user_provider, qualifier=provider_name).key
