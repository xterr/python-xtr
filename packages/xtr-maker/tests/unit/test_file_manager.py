"""Unit tests for :class:`xtr_maker.FileManager`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.captured_style import CapturedStyle
from tests.support.import_path import prepend_import_path
from xtr_maker import AppPackageNotFoundError, FileManager, UnsafePathError

if TYPE_CHECKING:
    from pathlib import Path


def test_the_package_is_found_where_it_is_imported_from(project: Path) -> None:
    assert FileManager(project, "app").package_dir == project.resolve() / "src" / "app"


@pytest.mark.usefixtures("importable")
def test_the_package_is_found_at_the_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "flat_app").mkdir()
    prepend_import_path(monkeypatch, tmp_path)

    assert FileManager(tmp_path, "flat_app").package_dir == tmp_path.resolve() / "flat_app"


@pytest.mark.usefixtures("importable")
def test_a_dotted_package_is_found_in_its_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src" / "acme_maker" / "shop").mkdir(parents=True)
    _ = (tmp_path / "src" / "acme_maker" / "shop" / "__init__.py").write_text("", encoding="utf-8")
    prepend_import_path(monkeypatch, tmp_path / "src")

    manager = FileManager(tmp_path, "acme_maker.shop")

    assert manager.package_dir == tmp_path.resolve() / "src/acme_maker/shop"


@pytest.mark.parametrize("package", ["no_such_maker_app", "no_such_maker_app.shop", "json.decoder"])
def test_a_package_not_importable_names_the_setting_to_change(tmp_path: Path, package: str) -> None:
    manager = FileManager(tmp_path, package)

    with pytest.raises(AppPackageNotFoundError, match=r"MakerConfig\.root_package") as raised:
        _ = manager.package_dir

    assert raised.value.root_package == package


def test_a_relative_path_is_taken_from_the_project(project: Path) -> None:
    manager = FileManager(project, "app")

    assert manager.absolute("src/app/x.py") == project.resolve() / "src/app/x.py"
    assert manager.relative(project / "src/app/x.py") == "src/app/x.py"


def test_a_path_climbing_out_of_the_project_is_refused(project: Path) -> None:
    with pytest.raises(UnsafePathError, match="outside the project"):
        _ = FileManager(project, "app").absolute("../elsewhere.py")


def test_exists_reports_files_on_disk(project: Path) -> None:
    manager = FileManager(project, "app")

    assert manager.exists("src/app/__init__.py")
    assert not manager.exists("src/app/missing.py")


def test_read_returns_the_text(project: Path) -> None:
    assert FileManager(project, "app").read("src/app/__init__.py") == '"""The app."""\n'


def test_dump_creates_the_file_and_its_folders_and_says_so(project: Path) -> None:
    style = CapturedStyle()

    FileManager(project, "app").dump("src/app/message/x.py", "x = 1\n", style.io)

    assert (project / "src/app/message/x.py").read_text(encoding="utf-8") == "x = 1\n"
    assert style.lines == ["created: src/app/message/x.py"]


def test_dump_with_other_content_updates_the_file(project: Path) -> None:
    style = CapturedStyle()

    FileManager(project, "app").dump("src/app/__init__.py", "x = 1\n", style.io)

    assert style.lines == ["updated: src/app/__init__.py"]


def test_dump_with_the_same_content_changes_nothing(project: Path) -> None:
    style = CapturedStyle()

    FileManager(project, "app").dump("src/app/__init__.py", '"""The app."""\n', style.io)

    assert style.lines == ["no change: src/app/__init__.py"]


def test_dump_refuses_a_symbolic_link(project: Path) -> None:
    (project / "src/app/link.py").symlink_to(project / "src/app/__init__.py")

    with pytest.raises(UnsafePathError, match="symbolic link"):
        FileManager(project, "app").dump("src/app/link.py", "x = 1\n", CapturedStyle().io)


def test_dump_refuses_a_folder_linked_out_of_the_project(
    project: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("outside")
    (project / "src/app/linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafePathError, match="outside the project"):
        FileManager(project, "app").dump("src/app/linked/x.py", "x = 1\n", CapturedStyle().io)

    assert not (outside / "x.py").exists()


def test_ensure_package_gives_every_new_folder_an_init(project: Path) -> None:
    style = CapturedStyle()

    FileManager(project, "app").ensure_package(project / "src/app/message/ordering", style.io)

    assert (project / "src/app/message/ordering/__init__.py").read_text(encoding="utf-8") == (
        '"""The ``app.message.ordering`` package."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "__all__: list[str] = []\n"
    )
    assert style.lines == [
        "created: src/app/message/__init__.py",
        "created: src/app/message/ordering/__init__.py",
    ]


def test_ensure_package_leaves_an_existing_init_alone(project: Path) -> None:
    (project / "src/app/message").mkdir()
    _ = (project / "src/app/message/__init__.py").write_text("# mine\n", encoding="utf-8")
    style = CapturedStyle()

    FileManager(project, "app").ensure_package(project / "src/app/message", style.io)

    assert (project / "src/app/message/__init__.py").read_text(encoding="utf-8") == "# mine\n"
    assert style.lines == []


def test_ensure_package_refuses_a_folder_outside_the_package(project: Path) -> None:
    with pytest.raises(UnsafePathError, match="outside the application package"):
        FileManager(project, "app").ensure_package(project / "config", CapturedStyle().io)
