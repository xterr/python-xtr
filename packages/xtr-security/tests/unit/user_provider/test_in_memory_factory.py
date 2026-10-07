"""The in-memory user-provider factory builds a provider from inline users."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from typing_extensions import override
from xtr_dependency_injection import Bundle, Kernel, as_bundle
from xtr_dependency_injection.testing import boot_for_test
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
