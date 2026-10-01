"""The user-provider configurations validate their own shape."""

from __future__ import annotations

import pytest

from xtr_security.bundle import (
    ChainUserProviderConfig,
    InMemoryUserProviderConfig,
    ServiceUserProviderConfig,
)
from xtr_security.exception import InvalidConfigurationError


class _Provider:
    """A stand-in provider class."""


def test_in_memory_defaults_to_no_users() -> None:
    assert InMemoryUserProviderConfig().users == {}


def test_a_chain_needs_a_provider() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = ChainUserProviderConfig(providers=())


def test_a_chain_keeps_its_providers() -> None:
    config = ChainUserProviderConfig(providers=("a", "b"))

    assert config.providers == ("a", "b")


def test_a_service_provider_needs_a_class() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = ServiceUserProviderConfig(service="not-a-class")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # the point of the test


def test_a_service_provider_keeps_its_class_and_qualifier() -> None:
    config = ServiceUserProviderConfig(_Provider, qualifier="main")

    assert config.service is _Provider
    assert config.qualifier == "main"
