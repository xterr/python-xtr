"""The user-provider wiring: each configured provider, aliased to the interface."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_security_core.user.user_provider_interface import UserProviderInterface

from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

    from xtr_security.bundle.security_config import SecurityConfig
    from xtr_security.user_provider import UserProviderFactoryInterface

__all__ = ["register_user_providers"]


def register_user_providers(services: ServiceConfigurator, config: SecurityConfig) -> None:
    """Register each configured user provider, aliased to the provider interface.

    A provider is registered under its factory's key and the provider name as
    qualifier, then aliased to
    :class:`~xtr_security_core.user.user_provider_interface.UserProviderInterface`
    under the same name, so a firewall and a chain resolve any provider uniformly
    by name.
    """
    factories = {factory.config_type: factory for factory in config.user_provider_factories}
    for name, provider_config in config.providers.items():
        factory = _match_factory(
            factories,
            provider_config,
            f'the user provider "{name}"',
        )
        key = factory.create(services, _NO_BUILDER, name, provider_config)
        services.alias(
            UserProviderInterface,
            key[0],
            alias_qualifier=name,
            target_qualifier=key[1],
        )


def _match_factory(
    factories: dict[type, UserProviderFactoryInterface],
    provider_config: object,
    described: str,
) -> UserProviderFactoryInterface:
    """Return the user-provider factory whose configuration type matches."""
    for config_type, factory in factories.items():
        if isinstance(provider_config, config_type):
            return factory
    raise InvalidConfigurationError(
        f"No user-provider factory handles {type(provider_config).__name__} for {described}.",
    )


# A sentinel where a factory's ``builder`` argument is not used: the built-in
# factories register services and read no other definitions.
_NO_BUILDER = cast("ContainerBuilder", cast("object", None))
