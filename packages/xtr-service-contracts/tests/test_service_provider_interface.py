from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_service_contracts import ServiceProviderInterface

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping


class FakeProvider(ServiceProviderInterface[str]):
    def __init__(self) -> None:
        self.services: dict[Hashable, str] = {}

    async def get(self, name: Hashable, /) -> str:
        if name not in self.services:
            raise LookupError(name)
        return self.services[name]

    def has(self, name: Hashable, /) -> bool:
        return name in self.services

    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return dict.fromkeys(self.services, str)


class NotAProvider:
    async def get(self) -> None: ...

    def has(self) -> None: ...


def test_a_dict_backed_fake_is_a_service_provider_interface() -> None:
    fake: object = FakeProvider()

    assert isinstance(fake, ServiceProviderInterface)


def test_a_class_missing_provided_services_is_not_a_service_provider_interface() -> None:
    almost: object = NotAProvider()

    assert not isinstance(almost, ServiceProviderInterface)


@pytest.mark.anyio
async def test_get_returns_the_service_named() -> None:
    provider = FakeProvider()
    provider.services["logger"] = "the-logger"

    assert await provider.get("logger") == "the-logger"


@pytest.mark.anyio
async def test_get_raises_a_lookup_error_for_an_unknown_name() -> None:
    provider = FakeProvider()

    with pytest.raises(LookupError):
        _ = await provider.get("missing")


def test_provided_services_maps_each_name_to_its_type() -> None:
    provider = FakeProvider()
    provider.services["logger"] = "the-logger"

    assert provider.provided_services() == {"logger": str}
