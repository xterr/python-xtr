from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from xtr_recipes.exception import UnsafePathError
from xtr_recipes.file_write import refuse_symlink, write_text

if TYPE_CHECKING:
    from pathlib import Path


def test_it_writes_the_content_creating_the_directories(tmp_path: Path) -> None:
    path = tmp_path / "src" / "app" / "config.py"

    write_text(path, "BODY\n")

    assert path.read_text(encoding="utf-8") == "BODY\n"


def test_a_private_file_is_created_owner_only(tmp_path: Path) -> None:
    path = tmp_path / ".env"

    write_text(path, "KEY=1\n", private=True)

    assert path.stat().st_mode & 0o777 == 0o600


def test_a_plain_file_is_not_forced_to_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "config.py"

    write_text(path, "BODY\n")

    assert path.stat().st_mode & 0o200


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_it_refuses_to_write_through_a_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    _ = outside.write_text("", encoding="utf-8")
    link = tmp_path / ".env"
    link.symlink_to(outside)

    with pytest.raises(UnsafePathError):
        write_text(link, "SECRET=1\n")

    assert outside.read_text(encoding="utf-8") == ""


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_refuse_symlink_raises_on_a_link(tmp_path: Path) -> None:
    target = tmp_path / "real"
    _ = target.write_text("", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(target)

    with pytest.raises(UnsafePathError):
        refuse_symlink(link)


def test_refuse_symlink_allows_a_plain_path(tmp_path: Path) -> None:
    refuse_symlink(tmp_path / "config.py")
