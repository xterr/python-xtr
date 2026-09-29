"""A prefixed adapter is held to the contract every adapter answers.

The point of running the shared suite through the decorator is that a caller
must not be able to tell it is there: the same behaviours, the same failures,
the same listings — only the files sit one path further down inside the backend.
Visibility runs on, because the adapter underneath has it and a decorator that
quietly lost it would pass a suite that skipped it.

The three capability behaviours are restated here rather than inherited. A
decorator answers to all three capabilities whatever it wraps, since what it
wraps is not known until it is there, so the shared suite's "does it offer
this?" question is always yes and the honest expectation is what each says when
the adapter underneath has nothing to offer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

import pytest
from typing_extensions import override

from tests.support.adapter_conformance import AdapterConformance
from xtr_storage.adapter.in_memory_adapter import InMemoryAdapter
from xtr_storage.adapter.path_prefixed_adapter import PathPrefixedAdapter
from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    UnableToGeneratePublicUrlError,
    UnableToGenerateTemporaryUrlError,
)
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface

_PREFIX = "some/prefix"


class TestPathPrefixedAdapterConformance(AdapterConformance):
    """Every shared behaviour, over an in-memory backend entered at a prefix."""

    supports_visibility: ClassVar[bool] = True

    @pytest.fixture
    async def adapter(self) -> AsyncIterator[StorageAdapterInterface]:
        subject = PathPrefixedAdapter(InMemoryAdapter(), _PREFIX)
        try:
            yield subject
        finally:
            await subject.close()

    @override
    async def test_it_provides_a_checksum_when_supported(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        assert isinstance(adapter, ChecksumProviderInterface)
        await adapter.write("checked.txt", b"digest me", Config())

        with pytest.raises(ChecksumAlgorithmNotSupportedError):
            _ = await adapter.checksum("checked.txt", Config())

    @override
    async def test_it_generates_a_public_url_when_supported(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        assert isinstance(adapter, PublicUrlGeneratorInterface)
        await adapter.write("pub.txt", b"public bytes", Config())

        with pytest.raises(UnableToGeneratePublicUrlError):
            _ = await adapter.public_url("pub.txt", Config())

    @override
    async def test_it_generates_a_temporary_url_when_supported(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        assert isinstance(adapter, TemporaryUrlGeneratorInterface)
        await adapter.write("temp.txt", b"temporary bytes", Config())
        expires_at = datetime.now(UTC) + timedelta(minutes=5)

        with pytest.raises(UnableToGenerateTemporaryUrlError):
            _ = await adapter.temporary_url("temp.txt", expires_at, Config())


class TestPathPrefixedAdapterStoresUnderThePrefix:
    """The one thing a caller cannot see through the decorator, checked from behind it."""

    pytestmark: ClassVar[pytest.MarkDecorator] = pytest.mark.anyio

    async def test_a_written_file_sits_under_the_prefix_in_the_backend(self) -> None:
        inner = InMemoryAdapter()
        adapter = PathPrefixedAdapter(inner, _PREFIX)

        await adapter.write("tenant.txt", b"payload", Config())

        assert await inner.read(f"{_PREFIX}/tenant.txt") == b"payload"
        assert not await inner.file_exists("tenant.txt")
        await adapter.close()
