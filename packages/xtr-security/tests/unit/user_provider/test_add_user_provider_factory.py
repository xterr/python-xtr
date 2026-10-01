"""The user-provider prepend helper appends a factory to the config's tuple."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security.bundle import SecurityConfig
from xtr_security.user_provider import UserProviderFactoryInterface
from xtr_security.user_provider.add_user_provider_factory import add_user_provider_factory

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey


@final
class _FakeUserProviderFactory(UserProviderFactoryInterface):
    """A fake user-provider factory the helper appends."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        return "fake_provider"

    @property
    @override
    def config_type(self) -> type:
        return object

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        provider_name: str,
        config: object,
    ) -> ServiceKey:
        del services, builder, provider_name, config
        return (object, None)


def test_add_user_provider_factory_appends_it() -> None:
    factory = _FakeUserProviderFactory()
    transform = add_user_provider_factory(factory)

    result = transform(SecurityConfig())

    assert isinstance(result, SecurityConfig)
    assert result.user_provider_factories[-1] is factory
