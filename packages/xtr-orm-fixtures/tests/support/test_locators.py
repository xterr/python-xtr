"""The fixed locator hands out its services by name, in the order given."""

from __future__ import annotations

import pytest

from tests.support.locators import locator

pytestmark = pytest.mark.anyio


async def test_it_names_and_builds_each_service_in_order() -> None:
    built = locator(str, {"b": "second", "a": "first"})

    assert "a" in built
    assert "c" not in built
    assert [pair async for pair in built] == [("b", "second"), ("a", "first")]
