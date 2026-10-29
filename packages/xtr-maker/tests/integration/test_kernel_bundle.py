"""The MakerBundle in a kernel: its services resolve against the application on disk."""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from xtr_dependency_injection import Kernel, unit_of_work

from tests.support.captured_style import CapturedStyle
from xtr_maker import ClassName, FileManager, Generator, TemplateRenderer
from xtr_maker.bundle import MakerBundle

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_SETTINGS = '''"""Write into another package."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_maker.bundle import MakerConfig


@configure
def maker() -> MakerConfig:
    return MakerConfig(root_package="{other}")
'''


@dataclass(frozen=True, slots=True)
class _Application:
    """An application on disk: its resolved project directory and its package's name."""

    project_dir: Path
    package: str

    def kernel(self, *resources: str) -> Kernel:
        return Kernel(
            self.package, env="test", bundles={MakerBundle: {"all": True}}, resources=resources
        )


@pytest.fixture
def application(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Application:
    """An application whose uniquely named package sits under ``src/``, importable.

    It also holds another importable package under ``lib/``, and a settings
    module pointing the makers at it, for a kernel to scan when the test wants it.
    """
    name = f"maker_app_{uuid4().hex}"
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
    package = tmp_path / "src" / name
    package.mkdir(parents=True)
    _ = (package / "__init__.py").write_text('"""An application."""\n', encoding="utf-8")
    settings = _SETTINGS.replace("{other}", f"{name}_other")
    _ = (package / "maker_settings.py").write_text(settings, encoding="utf-8")
    (tmp_path / "lib" / f"{name}_other").mkdir(parents=True)
    monkeypatch.setattr(sys, "path", [str(tmp_path / "src"), str(tmp_path / "lib"), *sys.path])
    importlib.invalidate_caches()
    return _Application(tmp_path.resolve(), name)


async def test_the_generator_writes_into_the_kernel_package(application: _Application) -> None:
    name = ClassName.create("note", root_package=application.package, kind="message")

    async with await application.kernel().boot() as booted, unit_of_work(booted.container) as unit:
        manager = await unit.get(FileManager)
        generator = await unit.get(Generator)
        _ = await unit.get(TemplateRenderer)
        _ = generator.dump_file(manager.package_dir / name.path, '"""A note."""\n')
        generator.write_changes(CapturedStyle().io)

    package_dir = application.project_dir / "src" / application.package
    assert manager.package_dir == package_dir
    assert generator.generated_files == (package_dir / "message" / "note.py",)
    assert manager.exists(package_dir / "message" / "note.py")
    assert manager.exists(package_dir / "message" / "__init__.py")


async def test_each_unit_of_work_gets_a_generator_with_its_own_queue(
    application: _Application,
) -> None:
    async with await application.kernel().boot() as booted:
        async with unit_of_work(booted.container, join=False) as unit:
            first = await unit.get(Generator)
            again = await unit.get(Generator)
        async with unit_of_work(booted.container, join=False) as unit:
            second = await unit.get(Generator)

    assert first is again
    assert first is not second


async def test_a_configured_root_package_replaces_the_kernel_package(
    application: _Application,
) -> None:
    kernel = application.kernel(f"{application.package}.maker_settings")

    async with await kernel.boot() as booted:
        manager = await booted.container.get(FileManager)

    assert manager.package_dir == application.project_dir / "lib" / f"{application.package}_other"


async def test_the_kernel_package_is_used_whatever_the_kernel_is_named(
    application: _Application,
) -> None:
    kernel = Kernel(
        application.package,
        name="shop",
        env="test",
        bundles={MakerBundle: {"all": True}},
        resources=(),
    )

    async with await kernel.boot() as booted:
        manager = await booted.container.get(FileManager)

    assert manager.root_package == application.package
    assert manager.package_dir == application.project_dir / "src" / application.package
