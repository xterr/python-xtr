"""The gcs adapter, held to the contract every adapter answers.

This runs only against a Google Cloud Storage emulator, named by the
``XTR_STORAGE_GCS_EMULATOR_HOST`` environment variable; with none set the whole
module is skipped, so the package gate never reaches a network. Visibility is
off — the store offers no single answer to map onto, so the adapter refuses and
the suite checks it refuses.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.support.adapter_conformance import AdapterConformance
from xtr_storage.adapter.gcs_adapter import GcsAdapter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface

_EMULATOR_HOST = os.environ.get("XTR_STORAGE_GCS_EMULATOR_HOST")

if _EMULATOR_HOST is None:
    pytest.skip(
        "set XTR_STORAGE_GCS_EMULATOR_HOST to run the gcs conformance suite",
        allow_module_level=True,
    )


class TestGcsAdapterConformance(AdapterConformance):
    """Every shared behaviour, over a bucket on the configured emulator."""

    supports_visibility: ClassVar[bool] = False

    @pytest.fixture
    async def adapter(self) -> AsyncIterator[StorageAdapterInterface]:
        bucket = f"xtr-storage-{uuid.uuid4().hex}"
        subject = GcsAdapter(
            bucket,
            project="xtr-storage-test",
            token="anon",  # noqa: S106 -- "anon" is gcsfs's anonymous-access token literal, not a secret
            endpoint_url=_EMULATOR_HOST,
        )
        try:
            yield subject
        finally:
            await subject.close()
