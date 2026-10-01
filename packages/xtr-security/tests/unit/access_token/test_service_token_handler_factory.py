"""The service token-handler factory returns the key of the app's own service."""

from __future__ import annotations

from typing import cast

from xtr_security.bundle import (
    ServiceTokenHandlerConfig,
    ServiceTokenHandlerFactory,
    TokenHandlerFactoryInterface,
)


class _Handler:
    """A stand-in handler class."""


def test_it_carries_its_interface_key_and_config() -> None:
    factory = ServiceTokenHandlerFactory()

    assert TokenHandlerFactoryInterface in type(factory).__mro__
    assert factory.key == "id"
    assert factory.config_type is ServiceTokenHandlerConfig


def test_it_returns_the_service_key() -> None:
    factory = ServiceTokenHandlerFactory()
    services = cast("object", None)
    builder = cast("object", None)

    key = factory.create(
        services,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        builder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_id",
        ServiceTokenHandlerConfig(_Handler, qualifier="main"),
    )

    assert key == (_Handler, "main")
