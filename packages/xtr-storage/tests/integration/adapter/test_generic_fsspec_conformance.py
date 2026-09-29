# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportAttributeAccessIssue=false
# fsspec ships no type information; the memory filesystem this module builds and
# the attributes it sets on it are untyped, so the directives above are confined
# to this one module.
"""The generic adapter, held to the contract every adapter answers.

The filesystem it is handed is a memory one with a store of its own — the
smallest real backend there is, and the point is the wrapping rather than the
backend. Visibility is off: an instance arriving from outside says nothing
about whether what is behind it has any, so the adapter refuses rather than
guesses, and the suite checks it refuses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from fsspec.implementations.memory import MemoryFileSystem

from tests.support.adapter_conformance import AdapterConformance
from xtr_storage.adapter.generic_fsspec_adapter import GenericFsspecAdapter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface


class TestGenericFsspecAdapterConformance(AdapterConformance):
    """Every shared behaviour, over a filesystem the test built itself."""

    supports_visibility: ClassVar[bool] = False

    @pytest.fixture
    async def adapter(self) -> AsyncIterator[StorageAdapterInterface]:
        filesystem = MemoryFileSystem(skip_instance_cache=True)
        filesystem.store = {}
        filesystem.pseudo_dirs = [""]
        subject = GenericFsspecAdapter(filesystem)
        try:
            yield subject
        finally:
            await subject.close()
