"""Unit tests for :class:`xtr_storage.bundle.StorageBundle`; no test reaches a server."""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config

from tests.fixtures.app_storage_reference.services import ADAPTER
from xtr_storage.adapter.path_prefixed_adapter import PathPrefixedAdapter
from xtr_storage.adapter.read_only_adapter import ReadOnlyAdapter
from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.bundle import StorageBundle
from xtr_storage.exception import InvalidArgumentError, UnableToWriteFileError
from xtr_storage.mount_manager import MountManager
from xtr_storage.storage import Storage
from xtr_storage.storage_operator_interface import StorageOperatorInterface
from xtr_storage.storage_reader_interface import StorageReaderInterface
from xtr_storage.storage_writer_interface import StorageWriterInterface

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_dependency_injection import BootedKernel

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_storage"

_STORAGE_NAMES = frozenset(
    {"default", "memory", "local", "s3", "fsspec", "gcs", "read_only", "prefixed", "public"},
)


def _kernel(tmp_path: Path, app: str = APP, **environ: str) -> Kernel:
    return Kernel(
        app,
        env="test",
        environ={"STORAGE_TEST_DIR": str(tmp_path / "local"), **environ},
    )


async def _storage(booted: BootedKernel, name: str) -> Storage:
    return await booted.container.get(Storage, name)


async def test_zero_config_builds_boots_and_shuts_down() -> None:
    await assert_zero_config(StorageBundle)


async def test_zero_config_creates_no_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def project_dir(_self: Kernel) -> Path:
        return tmp_path

    monkeypatch.setattr(Kernel, "project_dir", property(project_dir))
    kernel = Kernel(
        "xtr_storage.bundle",
        env="test",
        bundles={StorageBundle: {"all": True}},
        resources=(),
    )

    booted = await kernel.boot()
    await booted.shutdown()

    assert not (tmp_path / "var" / "storage").exists()


async def test_every_storage_is_provided_qualified_and_under_the_three_interfaces(
    tmp_path: Path,
) -> None:
    async with await _kernel(tmp_path).boot() as booted:
        for name in _STORAGE_NAMES:
            storage = await _storage(booted, name)
            for interface in (
                StorageOperatorInterface,
                StorageReaderInterface,
                StorageWriterInterface,
            ):
                assert await booted.container.get(interface, name) is storage


async def test_the_default_storage_is_provided_without_a_qualifier(tmp_path: Path) -> None:
    async with await _kernel(tmp_path).boot() as booted:
        default = await _storage(booted, "default")

        assert await booted.container.get(Storage) is default
        for interface in (
            StorageOperatorInterface,
            StorageReaderInterface,
            StorageWriterInterface,
        ):
            assert await booted.container.get(interface) is default


async def test_an_env_placeholder_in_the_configuration_is_resolved_at_build(
    tmp_path: Path,
) -> None:
    async with await _kernel(tmp_path).boot() as booted:
        local = await _storage(booted, "local")
        await local.write("greeting.txt", b"hi")

    assert (tmp_path / "local" / "greeting.txt").read_bytes() == b"hi"


async def test_a_read_only_storage_wraps_its_adapter_and_refuses_writes(tmp_path: Path) -> None:
    async with await _kernel(tmp_path).boot() as booted:
        storage = await _storage(booted, "read_only")

        assert isinstance(storage._adapter, ReadOnlyAdapter)
        with pytest.raises(UnableToWriteFileError):
            await storage.write("x.txt", b"y")


async def test_a_prefixed_storage_wraps_its_adapter(tmp_path: Path) -> None:
    async with await _kernel(tmp_path).boot() as booted:
        storage = await _storage(booted, "prefixed")

        assert isinstance(storage._adapter, PathPrefixedAdapter)


async def test_the_mount_manager_covers_every_storage(tmp_path: Path) -> None:
    async with await _kernel(tmp_path).boot() as booted:
        mount = await booted.container.get(MountManager)

        assert set(mount._storages) == _STORAGE_NAMES


async def test_a_referenced_adapter_is_the_one_the_storage_uses() -> None:
    app = "tests.fixtures.app_storage_reference"
    async with await Kernel(app, env="test").boot() as booted:
        storage = await booted.container.get(Storage, "default")
        adapter = await booted.container.get(StorageAdapterInterface, ADAPTER)

        assert storage._adapter is adapter

        await storage.write("note.txt", b"kept")
        assert await storage.read("note.txt") == b"kept"


async def test_boot_refuses_a_reference_the_container_does_not_provide() -> None:
    app = "tests.fixtures.app_storage_missing_reference"
    with pytest.raises(InvalidArgumentError, match=r'the "default" storage'):
        _ = await Kernel(app, env="test").boot()


async def test_boot_refuses_a_visibility_on_a_backend_without_one() -> None:
    app = "tests.fixtures.app_storage_bad_visibility"
    with pytest.raises(InvalidArgumentError, match=r'the "gcs" storage sets a visibility'):
        _ = await Kernel(app, env="test").boot()


async def test_boot_refuses_a_storage_whose_backend_is_not_installed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = importlib.util.find_spec

    def fake(name: str, package: str | None = None) -> object:
        if name == "gcsfs":
            return None
        return real(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake)

    with pytest.raises(InvalidArgumentError, match=r'the "gcs" storage needs the "gcsfs"'):
        _ = await _kernel(tmp_path).boot()


async def test_writing_through_a_storage_then_shutdown_closes_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[Storage] = []

    async def record(self: Storage) -> None:
        closed.append(self)

    monkeypatch.setattr(Storage, "close", record)

    async with await _kernel(tmp_path).boot() as booted:
        memory = await _storage(booted, "memory")
        await memory.write("a.txt", b"data")

    assert memory in closed
