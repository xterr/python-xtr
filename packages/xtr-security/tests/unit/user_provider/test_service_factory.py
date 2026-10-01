"""The service user-provider factory returns the key of the app's own service."""

from __future__ import annotations

from typing import cast

from xtr_security.bundle import (
    ServiceUserProviderConfig,
    ServiceUserProviderFactory,
    UserProviderFactoryInterface,
)


class _Provider:
    """A stand-in provider class."""


def test_it_carries_its_interface_key_and_config() -> None:
    factory = ServiceUserProviderFactory()

    assert UserProviderFactoryInterface in type(factory).__mro__
    assert factory.key == "service"
    assert factory.config_type is ServiceUserProviderConfig


def test_it_returns_the_service_key() -> None:
    factory = ServiceUserProviderFactory()
    services = cast("object", None)
    builder = cast("object", None)

    key = factory.create(
        services,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        builder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "users",
        ServiceUserProviderConfig(_Provider, qualifier="main"),
    )

    assert key == (_Provider, "main")
