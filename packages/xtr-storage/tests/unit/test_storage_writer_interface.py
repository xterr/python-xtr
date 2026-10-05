from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_storage.storage_writer_interface import StorageWriterInterface
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Iterable, Mapping
    from typing import BinaryIO


class FakeWriter:
    """Keeps what it was told to do, so a test can read the order back."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.calls: list[str] = []

    async def write(
        self,
        location: str,
        contents: bytes,
        config: Mapping[str, object] | None = None,
    ) -> None:
        del config

        self.files[location] = contents
        self.calls.append(f"write {location}")

    async def write_stream(
        self,
        location: str,
        contents: AsyncIterable[bytes] | Iterable[bytes] | BinaryIO,
        config: Mapping[str, object] | None = None,
    ) -> None:
        del contents, config

        self.calls.append(f"write_stream {location}")

    async def set_visibility(self, path: str, visibility: Visibility | str) -> None:
        self.calls.append(f"set_visibility {path} {Visibility.parse(visibility)}")

    async def delete(self, location: str) -> None:
        _ = self.files.pop(location, None)
        self.calls.append(f"delete {location}")

    async def delete_directory(self, location: str) -> None:
        self.calls.append(f"delete_directory {location}")

    async def create_directory(
        self,
        location: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        del config

        self.calls.append(f"create_directory {location}")

    async def move(
        self,
        source: str,
        destination: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        del config

        self.files[destination] = self.files.pop(source)
        self.calls.append(f"move {source} {destination}")

    async def copy(
        self,
        source: str,
        destination: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        del config

        self.files[destination] = self.files[source]
        self.calls.append(f"copy {source} {destination}")


def test_a_structural_match_satisfies_the_interface() -> None:
    assert isinstance(FakeWriter(), StorageWriterInterface)


def test_an_object_with_none_of_the_methods_does_not_satisfy_the_interface() -> None:
    class Empty:
        pass

    assert not isinstance(Empty(), StorageWriterInterface)


def test_writing_alone_does_not_satisfy_the_interface() -> None:
    class OnlyWrites:
        async def write(
            self,
            location: str,
            contents: bytes,
            config: Mapping[str, object] | None = None,
        ) -> None:
            del location, contents, config

    assert not isinstance(OnlyWrites(), StorageWriterInterface)


@pytest.mark.anyio
async def test_a_writer_is_driven_through_the_interface() -> None:
    fake = FakeWriter()
    writer: StorageWriterInterface = fake

    await writer.write("a.txt", b"contents")
    await writer.copy("a.txt", "b.txt")
    await writer.move("b.txt", "photos/c.txt")
    await writer.delete("a.txt")

    assert fake.files == {"photos/c.txt": b"contents"}


@pytest.mark.anyio
async def test_a_visibility_reaches_a_writer_by_name_or_by_member() -> None:
    fake = FakeWriter()
    writer: StorageWriterInterface = fake

    await writer.set_visibility("a.txt", "public")
    await writer.set_visibility("b.txt", Visibility.PRIVATE)

    assert fake.calls == ["set_visibility a.txt public", "set_visibility b.txt private"]
