"""The in-memory user-provider factory builds a provider from inline users."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, override

import pytest
from xtr_dependency_injection import Bundle, Kernel, as_bundle, env
from xtr_dependency_injection.exception import ServiceResolutionError
from xtr_dependency_injection.testing import boot_for_test
from xtr_security_core import InMemoryUser
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.user_provider_interface import UserProviderInterface

from xtr_security.bundle import (
    InMemoryUserProviderConfig,
    InMemoryUserProviderFactory,
    UserProviderFactoryInterface,
)

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

pytestmark = pytest.mark.anyio


def test_it_carries_its_interface_key_and_config() -> None:
    factory = InMemoryUserProviderFactory()

    assert UserProviderFactoryInterface in type(factory).__mro__
    assert factory.key == "in_memory"
    assert factory.config_type is InMemoryUserProviderConfig


@as_bundle("in_memory_probe")
class _ProbeBundle(Bundle):
    """Registers one in-memory provider through the factory under test."""

    @override
    def load_extension(
        self,
        config: object,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        del config
        key = InMemoryUserProviderFactory().create(
            services,
            builder,
            "users",
            InMemoryUserProviderConfig(
                users={"alice": {"password": "p", "roles": ["ROLE_USER"], "enabled": True}}
            ),
        )
        services.alias(
            UserProviderInterface,
            key[0],
            alias_qualifier="users",
            target_qualifier=key[1],
        )


async def test_it_builds_a_provider_that_loads_the_inline_user() -> None:
    kernel = Kernel(
        "tests.fixtures.probe_app",
        env="test",
        bundles={_ProbeBundle: {"all": True}},
    )
    async with await boot_for_test(kernel) as booted:
        provider = await booted.container.get(UserProviderInterface, "users")
        user = await provider.load_user_by_identifier("alice")

    assert user.get_user_identifier() == "alice"
    assert "ROLE_USER" in user.get_roles()


def test_a_non_boolean_enabled_flag_is_refused() -> None:
    factory = InMemoryUserProviderFactory()
    config = InMemoryUserProviderConfig(users={"alice": {"enabled": "false"}})
    services = cast("ServiceConfigurator", object())
    builder = cast("ContainerBuilder", object())

    with pytest.raises(InvalidArgumentError):
        _ = factory.create(services, builder, "users", config)


def _placeholder_bundle(users: dict[str, dict[str, object]]) -> type[Bundle]:
    @as_bundle("in_memory_placeholders")
    class PlaceholderBundle(Bundle):
        @override
        def load_extension(
            self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
        ) -> None:
            del config
            key = InMemoryUserProviderFactory().create(
                services, builder, "users", InMemoryUserProviderConfig(users=users)
            )
            services.alias(
                UserProviderInterface, key[0], alias_qualifier="users", target_qualifier=key[1]
            )

    return PlaceholderBundle


async def test_a_user_read_from_the_environment_carries_the_values_the_variables_hold() -> None:
    bundle = _placeholder_bundle(
        {"alice": {"password": env("ALICE_PASSWORD"), "roles": [env("ALICE_ROLE")]}}
    )
    kernel = Kernel(
        "tests.fixtures.probe_app",
        env="test",
        bundles={bundle: {"all": True}},
        environ={"ALICE_PASSWORD": "s3cret", "ALICE_ROLE": "ROLE_ADMIN"},
    )
    async with await boot_for_test(kernel) as booted:
        provider = await booted.container.get(UserProviderInterface, "users")
        user = await provider.load_user_by_identifier("alice")

    assert isinstance(user, InMemoryUser)
    assert user.get_password() == "s3cret"
    assert "ROLE_ADMIN" in user.get_roles()


async def test_a_user_read_from_the_environment_is_checked_when_the_provider_is_built() -> None:
    bundle = _placeholder_bundle({"alice": {"password": env("ALICE_PASSWORD"), "enabled": "false"}})
    kernel = Kernel(
        "tests.fixtures.probe_app",
        env="test",
        bundles={bundle: {"all": True}},
        environ={"ALICE_PASSWORD": "s3cret"},
    )
    # The table holds a placeholder: it builds, and the malformed user is refused at use.
    async with await boot_for_test(kernel) as booted:
        with pytest.raises(ServiceResolutionError, match="enabled flag") as caught:
            _ = await booted.container.get(UserProviderInterface, "users")

    assert isinstance(caught.value.__cause__, InvalidArgumentError)
