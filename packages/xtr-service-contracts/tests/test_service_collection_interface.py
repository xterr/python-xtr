from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_service_contracts import ServiceCollectionInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Hashable, Mapping


class FakeCollection(ServiceCollectionInterface[str]):
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

    def __len__(self) -> int:
        return len(self.services)

    def __aiter__(self) -> AsyncIterator[tuple[Hashable, str]]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[tuple[Hashable, str]]:
        for name in self.services:
            yield name, await self.get(name)


class NotACollection:
    async def get(self) -> None: ...

    def has(self) -> None: ...

    def provided_services(self) -> None: ...

    def __len__(self) -> int: ...


def test_a_dict_backed_fake_is_a_service_collection_interface() -> None:
    fake: object = FakeCollection()

    assert isinstance(fake, ServiceCollectionInterface)


def test_a_class_missing_aiter_is_not_a_service_collection_interface() -> None:
    almost: object = NotACollection()

    assert not isinstance(almost, ServiceCollectionInterface)


def test_len_counts_the_provided_services() -> None:
    collection = FakeCollection()
    collection.services["logger"] = "the-logger"
    collection.services["clock"] = "the-clock"

    assert len(collection) == 2


@pytest.mark.anyio
async def test_iterating_yields_name_service_pairs_in_order() -> None:
    collection = FakeCollection()
    collection.services["logger"] = "the-logger"
    collection.services["clock"] = "the-clock"

    pairs = [pair async for pair in collection]

    assert pairs == [("logger", "the-logger"), ("clock", "the-clock")]
