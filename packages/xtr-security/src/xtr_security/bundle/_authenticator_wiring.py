"""Registering a firewall's authenticators through their factories."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from xtr_dependency_injection import ServiceKey, named_factory
from xtr_security_core.user.missing_user_provider import MissingUserProvider
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http.authenticator.authenticator_interface import (
    AuthenticatorInterface,
)

from xtr_security.bundle._entry_point_wiring import entry_point_kind, resolve_entry_point
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory.stateless_authenticator_factory_interface import (
    StatelessAuthenticatorFactoryInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

    from xtr_security.access_token.token_handler_factory_interface import (
        TokenHandlerFactoryInterface,
    )
    from xtr_security.bundle.security_config import SecurityConfig
    from xtr_security.factory import AuthenticatorFactoryInterface
    from xtr_security.firewall_config import FirewallConfig

__all__ = ["register_authenticators"]


@runtime_checkable
class TakesTokenHandlerFactories(Protocol):
    """An authenticator factory that resolves token handlers through a registry.

    The access-token factory needs the token-handler factories to build its
    handler; another kind of authenticator factory does not. This is the shape
    the wiring tests for, instead of probing an attribute by name.
    """

    def with_token_handler_factories(
        self,
        token_handler_factories: Mapping[str, TokenHandlerFactoryInterface],
    ) -> AuthenticatorFactoryInterface:
        """Return a copy of the factory bound to ``token_handler_factories``."""
        ...


def register_authenticators(
    services: ServiceConfigurator,
    config: SecurityConfig,
    name: str,
    firewall: FirewallConfig,
    provider_qualifier: str | None,
) -> tuple[tuple[str, ...], str | None]:
    """Register the firewall's authenticators, aliased for collection, sorted by priority.

    Each authenticator is aliased to
    :class:`~xtr_security_http.authenticator.authenticator_interface.AuthenticatorInterface`
    under a qualifier of its own, so the context factory gathers them from a
    ``Mapping`` and picks this firewall's, in order. Returns those qualifiers and
    the one the entry point answers on.
    """
    factories = authenticator_factories(config)
    token_handler_factories = {factory.key: factory for factory in config.token_handler_factories}
    user_provider = (
        (UserProviderInterface, provider_qualifier) if provider_qualifier is not None else None
    )
    # With no provider named by the firewall nor configured at all, every
    # authenticator but a stateless one gets a placeholder that fails, naming
    # the firewall, the first time it is used.
    missing_user_provider = (
        register_missing_user_provider(services, name)
        if user_provider is None and not config.providers
        else None
    )
    keys: list[tuple[int, ServiceKey]] = []
    kinds: list[str] = []
    for authenticator_config in firewall.authenticators:
        factory = match_authenticator_factory(factories, authenticator_config, name)
        prepared = prepare_factory(factory, token_handler_factories)
        stateless = StatelessAuthenticatorFactoryInterface in type(prepared).__mro__
        created = prepared.create_authenticator(
            services,
            NO_BUILDER,
            name,
            authenticator_config,
            user_provider if stateless or missing_user_provider is None else missing_user_provider,
        )
        keys.extend((prepared.priority, key) for key in created)
        kinds.extend(entry_point_kind(prepared, authenticator_config) for _ in created)
    keys.sort(key=lambda entry: -entry[0])
    ordered = [key for _, key in keys]

    qualifiers: list[str] = []
    for index, key in enumerate(ordered):
        qualifier = f"{name}#authenticator#{index}"
        services.alias(
            AuthenticatorInterface,
            key[0],
            alias_qualifier=qualifier,
            target_qualifier=key[1],
        )
        qualifiers.append(qualifier)
    entry_point_qualifier = resolve_entry_point(config, name, firewall, ordered, qualifiers, kinds)
    return tuple(qualifiers), entry_point_qualifier


def register_missing_user_provider(services: ServiceConfigurator, name: str) -> ServiceKey:
    """Register the placeholder provider of the firewall ``name``, and return its key.

    It is a factory, so nothing is built — and nothing raises — until an
    authenticator asks for it.
    """
    qualifier = f"security.user.provider.missing.{name}"

    def missing_user_provider() -> MissingUserProvider:
        return MissingUserProvider(name)

    _ = services.set(
        named_factory(missing_user_provider, f"missing_user_provider_{name}"),
        qualifier=qualifier,
    )
    services.alias(
        UserProviderInterface,
        MissingUserProvider,
        alias_qualifier=qualifier,
        target_qualifier=qualifier,
    )
    return (UserProviderInterface, qualifier)


def prepare_factory(
    factory: AuthenticatorFactoryInterface,
    token_handler_factories: dict[str, TokenHandlerFactoryInterface],
) -> AuthenticatorFactoryInterface:
    """Give an access-token factory the token-handler registry it needs."""
    if isinstance(factory, TakesTokenHandlerFactories):
        return factory.with_token_handler_factories(token_handler_factories)
    return factory


def authenticator_factories(
    config: SecurityConfig,
) -> dict[type, AuthenticatorFactoryInterface]:
    """Index the authenticator factories by their configuration type."""
    return {factory.config_type: factory for factory in config.authenticator_factories}


def match_authenticator_factory(
    factories: dict[type, AuthenticatorFactoryInterface],
    authenticator_config: object,
    firewall_name: str,
) -> AuthenticatorFactoryInterface:
    """Return the factory whose configuration type matches, or fail the build."""
    for config_type, factory in factories.items():
        if isinstance(authenticator_config, config_type):
            return factory
    raise InvalidConfigurationError(
        f"No authenticator factory handles {type(authenticator_config).__name__} "
        f'on the firewall "{firewall_name}".',
    )


# A sentinel where a factory's ``builder`` argument is not used: the built-in
# factories register services and read no other definitions.
NO_BUILDER = cast("ContainerBuilder", cast("object", None))
