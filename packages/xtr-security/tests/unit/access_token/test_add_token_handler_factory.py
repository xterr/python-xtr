"""The token-handler prepend helper appends a factory to the config's tuple."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security.access_token import TokenHandlerFactoryInterface
from xtr_security.access_token.add_token_handler_factory import add_token_handler_factory
from xtr_security.bundle import SecurityConfig

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey


@final
class _FakeTokenHandlerFactory(TokenHandlerFactoryInterface):
    """A fake token-handler factory the helper appends."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        return "fake_handler"

    @property
    @override
    def config_type(self) -> type:
        return object

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        service_id: str,
        config: object,
    ) -> ServiceKey:
        del services, builder, service_id, config
        return (object, None)


def test_add_token_handler_factory_appends_it() -> None:
    factory = _FakeTokenHandlerFactory()
    transform = add_token_handler_factory(factory)

    result = transform(SecurityConfig())

    assert isinstance(result, SecurityConfig)
    assert result.token_handler_factories[-1] is factory
