# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false
# fsspec ships no type information; the memory filesystem this module builds and
# the attributes it sets on it are untyped, so the directives above are confined
# to this one module.
"""The conformance suite runs green over the base and red over a broken adapter.

Two proofs in one file. A minimal :class:`FsspecAdapter` over an instance-local
memory filesystem passes every behaviour in :class:`AdapterConformance`, which
is how the base is tested at all — no backend of its own, so the suite is run
against the smallest real one. And an adapter deliberately broken — its ``read``
hands back nothing — makes the read behaviour fail, proving the suite would
catch a backend that lied.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from fsspec.implementations.memory import MemoryFileSystem
from typing_extensions import override

from tests.support.adapter_conformance import AdapterConformance
from xtr_storage.adapter.fsspec_adapter import FsspecAdapter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fsspec import AbstractFileSystem

    from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface

pytestmark = pytest.mark.anyio


class _MemoryFsspecAdapter(FsspecAdapter):
    """A base adapter over a memory filesystem whose store is its own.

    Assigning a fresh ``store`` and ``pseudo_dirs`` on the instance keeps it off
    the class-wide dictionaries fsspec's memory filesystem shares, so two of
    these never see each other's files.
    """

    @override
    def _create_filesystem(self) -> AbstractFileSystem:
        filesystem = MemoryFileSystem(skip_instance_cache=True)
        filesystem.store = {}
        filesystem.pseudo_dirs = [""]
        return filesystem


class _BrokenReadAdapter(_MemoryFsspecAdapter):
    """The same, but its ``read`` always answers with nothing."""

    @override
    async def read(self, path: str) -> bytes:
        _ = await super().read(path)
        return b""


class TestMemoryBackedFsspecAdapter(AdapterConformance):
    """The base adapter, proved against the whole suite over a memory backend."""

    supports_visibility: ClassVar[bool] = False

    @pytest.fixture
    async def adapter(self) -> AsyncIterator[StorageAdapterInterface]:
        subject = _MemoryFsspecAdapter()
        try:
            yield subject
        finally:
            await subject.close()


async def test_the_suite_fails_a_broken_adapter() -> None:
    broken = _BrokenReadAdapter()

    with pytest.raises(AssertionError):
        await AdapterConformance().test_it_reads_back_what_it_wrote(broken)

    await broken.close()
