from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.unit.test_storage_reader_interface import FakeReader
from tests.unit.test_storage_writer_interface import FakeWriter
from xtr_storage.storage_operator_interface import StorageOperatorInterface
from xtr_storage.storage_reader_interface import StorageReaderInterface
from xtr_storage.storage_writer_interface import StorageWriterInterface

if TYPE_CHECKING:
    from collections.abc import Mapping


class ReadsAndWrites(FakeReader, FakeWriter):
    """Both halves of a storage and nothing else."""


class FakeOperator(ReadsAndWrites):
    """Both halves, plus the addresses only a whole storage hands out."""

    async def public_url(self, path: str, config: Mapping[str, object] | None = None) -> str:
        del config

        return f"https://files.example/{path}"

    async def temporary_url(
        self,
        path: str,
        expires_at: datetime,
        config: Mapping[str, object] | None = None,
    ) -> str:
        del config

        return f"https://files.example/{path}?until={int(expires_at.timestamp())}"

    async def checksum(self, path: str, config: Mapping[str, object] | None = None) -> str:
        del config

        return f"{len(path):032x}"


def test_a_structural_match_satisfies_the_interface() -> None:
    assert isinstance(FakeOperator(), StorageOperatorInterface)


def test_reading_and_writing_alone_does_not_satisfy_the_interface() -> None:
    assert not isinstance(ReadsAndWrites(), StorageOperatorInterface)


def test_an_operator_also_satisfies_each_half() -> None:
    operator = FakeOperator()

    assert isinstance(operator, StorageReaderInterface)
    assert isinstance(operator, StorageWriterInterface)


def test_the_interface_inherits_both_halves() -> None:
    assert issubclass(StorageOperatorInterface, (StorageReaderInterface, StorageWriterInterface))


@pytest.mark.anyio
async def test_an_operator_reads_and_writes_through_the_interface() -> None:
    fake = FakeOperator()
    operator: StorageOperatorInterface = fake

    await operator.write("a.txt", b"contents")

    assert fake.files == {"a.txt": b"contents"}
    assert await operator.read("a.txt") == b"a.txt"


@pytest.mark.anyio
async def test_an_operator_hands_out_addresses_through_the_interface() -> None:
    operator: StorageOperatorInterface = FakeOperator()
    expires_at = datetime(2030, 1, 1, tzinfo=UTC)

    assert await operator.public_url("a.txt") == "https://files.example/a.txt"
    assert await operator.temporary_url("a.txt", expires_at) == (
        f"https://files.example/a.txt?until={int(expires_at.timestamp())}"
    )
    assert await operator.checksum("a.txt") == f"{5:032x}"
