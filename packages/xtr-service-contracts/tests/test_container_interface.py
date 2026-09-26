from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, cast

import pytest

from xtr_service_contracts import ContainerInterface

if TYPE_CHECKING:
    from collections.abc import Hashable

T = TypeVar("T")


class FakeContainer(ContainerInterface):
    def __init__(self) -> None:
        self.services: dict[tuple[type[object], Hashable | None], object] = {}
        self.parameters: dict[str, object] = {}

    async def get(self, service: type[T], /, qualifier: Hashable | None = None) -> T:
        if (service, qualifier) not in self.services:
            raise LookupError(service)
        return cast("T", self.services[service, qualifier])

    def has(self, service: type[object], /, qualifier: Hashable | None = None) -> bool:
        return (service, qualifier) in self.services

    def get_parameter(self, name: str, /) -> object:
        if name not in self.parameters:
            raise LookupError(name)
        return self.parameters[name]

    def has_parameter(self, name: str, /) -> bool:
        return name in self.parameters


class NotAContainer:
    async def get(self) -> None: ...

    def has(self) -> None: ...

    def get_parameter(self) -> None: ...


def test_a_dict_backed_fake_is_a_container_interface() -> None:
    fake: object = FakeContainer()

    assert isinstance(fake, ContainerInterface)


def test_a_class_missing_has_parameter_is_not_a_container_interface() -> None:
    almost: object = NotAContainer()

    assert not isinstance(almost, ContainerInterface)


@pytest.mark.anyio
async def test_get_returns_the_registered_service() -> None:
    container = FakeContainer()
    marker = object()
    container.services[object, None] = marker

    assert await container.get(object) is marker


@pytest.mark.anyio
async def test_get_raises_a_lookup_error_when_the_service_is_absent() -> None:
    container = FakeContainer()

    with pytest.raises(LookupError):
        _ = await container.get(object)


def test_parameters_are_read_by_dotted_name() -> None:
    container = FakeContainer()
    container.parameters["kernel.debug"] = True

    assert container.has_parameter("kernel.debug")
    assert container.get_parameter("kernel.debug") is True
    assert not container.has_parameter("kernel.name")
