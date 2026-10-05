"""The in-memory adapter, held to the contract every adapter answers.

It is the one backend that has visibility without a permission system behind
it, so the suite runs with visibility on: what it remembers has to survive a
copy and a move exactly as a mode bit or an access list would.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.support.adapter_conformance import AdapterConformance
from xtr_storage.adapter.in_memory_adapter import InMemoryAdapter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface


class TestInMemoryAdapterConformance(AdapterConformance):
    """Every shared behaviour, over a store this class alone can reach."""

    supports_visibility: ClassVar[bool] = True

    @pytest.fixture
    async def adapter(self) -> AsyncIterator[StorageAdapterInterface]:
        subject = InMemoryAdapter()
        try:
            yield subject
        finally:
            await subject.close()
