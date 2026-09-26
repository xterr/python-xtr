from __future__ import annotations

import pytest

from tests.support.in_memory_pool import InMemoryPool
from xtr_cache_contracts import RESERVED_CHARACTERS, ItemInterface

pytestmark = pytest.mark.anyio


async def test_an_item_a_pool_hands_out_satisfies_it() -> None:
    assert isinstance(await InMemoryPool().get_item("k"), ItemInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), ItemInterface)


def test_the_reserved_characters_are_the_ones_pools_structure_keys_with() -> None:
    assert set(RESERVED_CHARACTERS) == set("{}()/\\@:")
