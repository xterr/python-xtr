"""The local adapter, held to the contract every adapter answers.

A real directory on a real disk, which is why this lives among the integration
tests: every behaviour here goes through the filesystem, and the permission bits
the suite round-trips are the operating system's own. Each test gets a directory
of its own, and the adapter creates it on its first write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.support.adapter_conformance import AdapterConformance
from xtr_storage.adapter.local_adapter import LocalAdapter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface


class TestLocalAdapterConformance(AdapterConformance):
    """Every shared behaviour, over a directory this test alone can reach."""

    supports_visibility: ClassVar[bool] = True

    @pytest.fixture
    async def adapter(self, tmp_path: Path) -> AsyncIterator[StorageAdapterInterface]:
        subject = LocalAdapter(tmp_path / "storage")
        try:
            yield subject
        finally:
            await subject.close()
