"""The chain user-provider factory builds a chain over the named providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_dependency_injection import Bundle, Kernel, as_bundle
from xtr_dependency_injection.testing import boot_for_test
from xtr_security_core.user.user_provider_interface import UserProviderInterface

from xtr_security.bundle import (
    ChainUserProviderConfig,
    ChainUserProviderFactory,
    InMemoryUserProviderConfig,
    InMemoryUserProviderFactory,
)

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

pytestmark = pytest.mark.anyio


def test_it_carries_its_key_and_config() -> None:
    factory = ChainUserProviderFactory()

    assert factory.key == "chain"
    assert factory.config_type is ChainUserProviderConfig


def _register_chain(
    services: ServiceConfigurator,
    builder: ContainerBuilder,
    name: str,
    members: tuple[str, ...],
) -> None:
    """Register a chain named ``name`` over ``members``, aliased the way the bundle does."""
    key = ChainUserProviderFactory().create(
        services,
        builder,
        name,
        ChainUserProviderConfig(providers=members),
    )
    services.alias(
        UserProviderInterface,
        key[0],
        alias_qualifier=name,
        target_qualifier=key[1],
    )


@as_bundle("chain_probe")
class _ProbeBundle(Bundle):
    """Registers an in-memory provider, a chain over it, and a chain over that chain."""

    @override
    def load_extension(
        self,
        config: object,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        del config
        inner = InMemoryUserProviderFactory().create(
            services,
            builder,
            "in_memory",
            InMemoryUserProviderConfig(users={"bob": {"roles": ["ROLE_USER"]}}),
        )
        services.alias(
            UserProviderInterface,
            inner[0],
            alias_qualifier="in_memory",
            target_qualifier=inner[1],
        )
        _register_chain(services, builder, "chain", ("in_memory",))
        _register_chain(services, builder, "outer", ("chain",))


def _kernel() -> Kernel:
    return Kernel(
        "tests.fixtures.probe_app",
        env="test",
        bundles={_ProbeBundle: {"all": True}},
    )


async def test_it_builds_a_chain_that_loads_through_the_named_provider() -> None:
    async with await boot_for_test(_kernel()) as booted:
        provider = await booted.container.get(UserProviderInterface, "chain")
        user = await provider.load_user_by_identifier("bob")

    assert user.get_user_identifier() == "bob"


async def test_a_chain_naming_another_chain_loads_through_the_inner_chains_members() -> None:
    async with await boot_for_test(_kernel()) as booted:
        provider = await booted.container.get(UserProviderInterface, "outer")
        user = await provider.load_user_by_identifier("bob")

    assert user.get_user_identifier() == "bob"
