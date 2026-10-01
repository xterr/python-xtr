"""The access-token factory builds a bearer authenticator, or fails on a bad handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_dependency_injection import Bundle, Kernel, as_bundle
from xtr_security_http import AccessTokenAuthenticator

from xtr_security.bundle import (
    AccessTokenConfig,
    AccessTokenFactory,
    AuthenticatorFactoryInterface,
    ServiceTokenHandlerConfig,
    ServiceTokenHandlerFactory,
)
from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

pytestmark = pytest.mark.anyio


def test_it_carries_its_interface_key_and_config() -> None:
    factory = AccessTokenFactory()

    assert AuthenticatorFactoryInterface in type(factory).__mro__
    assert factory.key == "access_token"
    assert factory.config_type is AccessTokenConfig
    assert isinstance(factory.priority, int)


class _Handler:
    """A stand-in handler class the service token-handler config names."""


@as_bundle("access_token_probe")
class _ProbeBundle(Bundle):
    """Builds an access-token authenticator through the factory under test."""

    @override
    def load_extension(
        self,
        config: object,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        del config
        factory = AccessTokenFactory().with_token_handler_factories(
            {"id": ServiceTokenHandlerFactory()}
        )
        _ = services.instance(_Handler())
        keys = factory.create_authenticator(
            services,
            builder,
            "api",
            AccessTokenConfig(token_handler=ServiceTokenHandlerConfig(_Handler)),
            None,
        )
        assert keys[0][0] is AccessTokenAuthenticator


async def test_it_builds_an_access_token_authenticator() -> None:
    kernel = Kernel(
        "tests.fixtures.probe_app",
        env="test",
        bundles={_ProbeBundle: {"all": True}},
    )
    _ = kernel.build()


def test_an_unknown_token_handler_config_fails() -> None:
    factory = AccessTokenFactory().with_token_handler_factories({})

    class _Unknown:
        type: str = "unknown"

    with pytest.raises(InvalidConfigurationError):
        _ = factory._build_handler(  # a direct call to reach the no-factory branch
            _NoServices(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            _NoBuilder(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "api",
            AccessTokenConfig(token_handler=_Unknown()),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        )


class _NoServices:
    """A services stand-in the no-factory branch never touches."""


class _NoBuilder:
    """A builder stand-in the no-factory branch never touches."""
