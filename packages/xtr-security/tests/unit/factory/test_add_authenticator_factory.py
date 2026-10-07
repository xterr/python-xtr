"""The authenticator prepend helper appends a factory, leaving the rest alone."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from xtr_security.bundle import SecurityConfig
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import AuthenticatorFactoryInterface
from xtr_security.factory.add_authenticator_factory import add_authenticator_factory

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey


@final
class _FakeAuthenticatorFactory(AuthenticatorFactoryInterface):
    """A fake authenticator factory the helper appends."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        return "fake_oauth2"

    @property
    @override
    def priority(self) -> int:
        return 10

    @property
    @override
    def config_type(self) -> type:
        return object

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        del services, builder, firewall_name, config, user_provider
        return ()


def test_add_authenticator_factory_appends_it() -> None:
    factory = _FakeAuthenticatorFactory()
    transform = add_authenticator_factory(factory)

    result = transform(SecurityConfig())

    assert isinstance(result, SecurityConfig)
    assert result.authenticator_factories[-1] is factory


def test_it_leaves_the_other_tuples_alone() -> None:
    factory = _FakeAuthenticatorFactory()
    before = SecurityConfig()

    after = add_authenticator_factory(factory)(before)

    assert isinstance(after, SecurityConfig)
    assert after.token_handler_factories == before.token_handler_factories
    assert after.user_provider_factories == before.user_provider_factories


def test_a_duplicate_factory_key_is_refused() -> None:
    factory = _FakeAuthenticatorFactory()
    once = add_authenticator_factory(factory)(SecurityConfig())

    with pytest.raises(InvalidConfigurationError):
        _ = add_authenticator_factory(_FakeAuthenticatorFactory())(once)
