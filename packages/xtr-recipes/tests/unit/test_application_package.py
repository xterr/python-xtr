from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support import write_package
from xtr_recipes.application_package import ApplicationPackage
from xtr_recipes.exception import ProjectNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

_SKIPPED = ("venv", "node_modules", "tests", "build", "dist", "site", "migrations", "var")


def test_it_finds_the_package_under_src(tmp_path: Path) -> None:
    package = write_package(tmp_path / "src", "shop")

    assert ApplicationPackage.find(tmp_path) == ApplicationPackage("shop", package)


def test_it_finds_the_package_at_the_project_root(tmp_path: Path) -> None:
    package = write_package(tmp_path, "shop")

    assert ApplicationPackage.find(tmp_path) == ApplicationPackage("shop", package)


def test_it_names_a_nested_package_by_its_dotted_path(tmp_path: Path) -> None:
    package = write_package(tmp_path / "src", "acme.shop")

    assert ApplicationPackage.find(tmp_path) == ApplicationPackage("acme.shop", package)


def test_a_package_under_src_wins_over_one_at_the_root(tmp_path: Path) -> None:
    package = write_package(tmp_path / "src", "shop")
    _ = write_package(tmp_path, "tooling")

    assert ApplicationPackage.find(tmp_path).directory == package


def test_the_packages_beside_the_application_do_not_count(tmp_path: Path) -> None:
    _ = write_package(tmp_path / "src", "fulltext", kernel=False)
    package = write_package(tmp_path / "src", "shop")

    assert ApplicationPackage.find(tmp_path).directory == package


def test_a_kernel_module_inside_the_application_does_not_count(tmp_path: Path) -> None:
    package = write_package(tmp_path / "src", "shop")
    _ = write_package(tmp_path / "src", "shop.http", kernel=False)
    _ = (package / "http" / "kernel.py").write_text("", encoding="utf-8")

    assert ApplicationPackage.find(tmp_path).name == "shop"


def test_a_kernel_in_a_directory_that_is_not_a_package_is_ignored(tmp_path: Path) -> None:
    scripts = tmp_path / "src" / "scripts"
    scripts.mkdir(parents=True)
    _ = (scripts / "kernel.py").write_text("", encoding="utf-8")
    package = write_package(tmp_path / "src", "shop")

    assert ApplicationPackage.find(tmp_path).directory == package


def test_a_kernel_below_a_plain_directory_is_ignored(tmp_path: Path) -> None:
    # src/plain/ has no __init__.py, so src/plain/shop/ is not importable as plain.shop.
    _ = write_package(tmp_path / "src" / "plain", "shop")

    with pytest.raises(ProjectNotFoundError):
        _ = ApplicationPackage.find(tmp_path)


@pytest.mark.parametrize("name", [*_SKIPPED, ".hidden"])
def test_a_skipped_directory_is_not_searched(tmp_path: Path, name: str) -> None:
    skipped = tmp_path / name
    skipped.mkdir()
    _ = (skipped / "__init__.py").write_text("", encoding="utf-8")
    _ = (skipped / "kernel.py").write_text("", encoding="utf-8")
    package = write_package(tmp_path, "shop")

    assert ApplicationPackage.find(tmp_path).directory == package


def test_it_raises_when_no_package_holds_a_kernel(tmp_path: Path) -> None:
    _ = write_package(tmp_path / "src", "shop", kernel=False)

    with pytest.raises(ProjectNotFoundError) as exc:
        _ = ApplicationPackage.find(tmp_path)

    assert exc.value.directory == tmp_path
    assert "no kernel.py was found" in exc.value.reason


def test_it_raises_listing_every_package_when_several_hold_a_kernel(tmp_path: Path) -> None:
    _ = write_package(tmp_path / "src", "shop")
    _ = write_package(tmp_path / "src", "acme.admin")

    with pytest.raises(ProjectNotFoundError) as exc:
        _ = ApplicationPackage.find(tmp_path)

    assert "acme.admin (src/acme/admin/)" in exc.value.reason
    assert "shop (src/shop/)" in exc.value.reason
